from flask import Flask, render_template, request, redirect, url_for
import google.generativeai as genai
from googlesearch import search
import psycopg2
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import redis
import requests
from datetime import datetime


app = Flask(__name__)
database_password = os.getenv('DATABASE_PASSWORD')
api_key = os.getenv("API_KEY")
redis_pass = os.getenv("REDIS_PASS")

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.0-flash-exp")

# Initialize Redis for IP tracking
redis_client = redis.Redis(
    host='redis-11307.c301.ap-south-1-1.ec2.redns.redis-cloud.com',
    port=11307,
    decode_responses=True,
    username="default",
    password=f"{redis_pass}",
)

# Set up rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["10 per minute"],   
)

def get_geolocation(ip):
    try:
        response = requests.get(f"https://ipinfo.io/{ip}/json", timeout=5)
        data = response.json()
        return data.get("country", "Unknown"), data.get("region", "Unknown")
    except Exception:
        return "Unknown", "Unknown"

def connect_to_library_db():
    return psycopg2.connect(
            host="aws-0-ap-southeast-1.pooler.supabase.com",  
            database="postgres",                            
            user="postgres.fxtisfulbcghgrljxblf", 
            port="6543",                                    
            password=f"{database_password}"                  
        )

def clean_response(response_text):
    cleaned_text = response_text.replace("*", "").replace("#", "").strip()
    return cleaned_text

@app.route('/', methods=['GET', 'POST'])
@limiter.limit("10 per minute")  # Apply rate limiting
def index():
    ip_address = request.remote_addr
    user_agent = request.headers.get("User-Agent", "Unknown")
    country, region = get_geolocation(ip_address)
    timestamp = datetime.utcnow().isoformat()
    redis_key = f"ip:{ip_address}:data"
    existing_data = redis_client.hgetall(redis_key)
    first_visit = existing_data.get("first_visit", timestamp)
    visits = int(existing_data.get("visits", 0)) + 1
    redis_client.hset(redis_key, mapping={
        "first_visit": first_visit,
        "last_visit": timestamp,
        "visits": visits,
        "user_agent": user_agent,
        "country": country,
        "region": region,
    })
    redis_client.persist(redis_key)

    if request.method == 'POST':
        search_type = request.form.get('search_type')
        search_input = request.form.get('search_input').strip()
        return redirect(url_for('result', search_type=search_type, search_input=search_input))
    return render_template('index.html')

@app.route('/result')
def result():
    search_type = request.args.get('search_type')
    search_input = request.args.get('search_input')
    original_input = request.args.get('original_input', None)

    db_connection = connect_to_library_db()
    cursor = db_connection.cursor()

    
    search_input_upper = search_input.upper()

    results = []
    cleaned_response = ""
    links = []

    if search_type == "Search by Author":
        query = """
        SELECT "BK_NAME", "BK_ID", "BOOK_STATUS", "AUTHOR_NAME"
        FROM library
        WHERE similarity("AUTHOR_NAME", %s) > 0.3
           OR "AUTHOR_NAME" ILIKE %s;
        """
        cursor.execute(query, (f"{search_input_upper}",f"%{search_input_upper}%"))
        books = cursor.fetchall()

        if books:
            for book in books:
                bk_name, bk_id, bk_status, author_name = book
                results.append({
                    "bk_name": bk_name,
                    "bk_id": bk_id,
                    "bk_status": bk_status,
                    "author_name": author_name
                })

        else:
            pass
        # Handle the case where no books are found
        response = model.generate_content(
            f"Get details about the author {search_input} and books by the author."
            "If the author name is invalid or not found include 'No Information found about the author' in your response."

        )
        cleaned_response = clean_response(response.text)

        if "No Information found about the author" in cleaned_response:
            # If AI says no results, perform a web search
            links = list(search(f"Details about the author '{search_input_upper}'", num_results=3))
            cleaned_response = f"No results found for the author '{search_input}'. Refer to the related links below."

        # return a response for Search by Author
        return render_template(
            'result.html',
            results=results,
            generated_info=cleaned_response,
            search_input=search_input,
            original_input=original_input,
            links=links
        )


    elif search_type == "Search by Book":
        query = """
        SELECT "BK_NAME", "BK_ID", "BOOK_STATUS", "AUTHOR_NAME"
        FROM library
        WHERE similarity("BK_NAME", %s) > 0.3
           OR "BK_NAME" ILIKE %s;
        """
        cursor.execute(query, (f"{search_input_upper}",f"%{search_input_upper}%"))
        books = cursor.fetchall()

        results = []
        if books:
            for book in books:
                bk_name, bk_id, bk_status, author_name = book
                output = {
                    "bk_name": bk_name,
                    "bk_id": bk_id,
                    "bk_status": bk_status,
                    "author_name": author_name,
                }
                results.append(output)

        else:
            pass

        # Generate AI response about the book and the author regardless of book presence
        response = model.generate_content(
            f"Get a summary of the Novel '{search_input}' and information about the author. "
             # "nothing other than the summary of the Novel/book and information about the author should be included in the output. "
             # "Also triple check if the author name is correct. Do not make a mistake. "
             # "Present the Summary in a clear and enagaing way. There should be a heading for the summary on the top. " 
             # "If the book name is invalid or not found include 'No summary found' in your response."
        )

        cleaned_response = clean_response(response.text)


        if "No summary found" in cleaned_response:
            bk_links = []
            # Search online for additional details when no summary is found
            bk_links = list(search(f"Get summary of the novel '{search_input_upper}'", num_results=3))

            # Update response to include a note about related links
            cleaned_response = f"No summary found for the book '{search_input}'. Refer to the related links below for more information."

            return render_template(
                'result.html',
                results=results,  # Pass any database results or an empty list if none
                generated_info=cleaned_response,  # Message about missing summary
                search_input=search_input,
                original_input=original_input,
                links=bk_links  # Pass related links
            )
        else:
            return render_template(
                'result.html',
                results=results,  # Pass database results
                generated_info=cleaned_response,  # AI-generated response
                search_input=search_input,
                original_input=original_input,
                links=[]  # No links since AI provided a response
            )

    cursor.close()
    db_connection.close()


@app.route('/contribute', methods=['GET', 'POST'])


def contribution():
    if request.method == 'POST':
        book_name = request.form.get('book_name').strip()
        author_name = request.form.get('author_name').strip()
        card_id = request.form.get('card_id').strip()

        db_connection = connect_to_library_db()
        cursor = db_connection.cursor()

        try:
            # Check if the card ID exists in the 'user' table
            query = """SELECT "CARD_ID" FROM "user" WHERE "CARD_ID" = %s;"""
            cursor.execute(query, (card_id,))
            user = cursor.fetchone()

            if not user:
                message = "Error: Your card ID is not present in the database."
            else:
                # Insert the book details into the 'contributed' table
                insert_query = """
                INSERT INTO "contributed" ("book", "author", "contributed_by", "DATE")
                VALUES (%s, %s, %s, CURRENT_DATE);
                """
                cursor.execute(insert_query, (book_name, author_name, card_id))
                db_connection.commit()

                # Success message
                message = (
                    f"Thank you for contributing '{book_name}' by {author_name}! "
                    "Your contribution data has been recorded. Once the book is received by the librarian, it will be added to the library's collection. "
                    "You will then earn 2 additional credits on top of your default credit of 2 for each book you contribute. "
                    "These credits will allow you to reserve an equal number of books per week. Please note that this cycle resets every Sunday."
                )

        except Exception as e:
            app.logger.error(f"Error during contribution: {e}")
            message = "An error occurred while processing your contribution."

        finally:
            cursor.close()
            db_connection.close()

        return render_template('contribution_result.html', message=message)

    return render_template('contribute.html')

@app.route('/reserve', methods=['GET', 'POST'])

def reserve_book():
    # Initialize the db connection and cursor outside of the method block
    db_connection = connect_to_library_db()
    cursor = db_connection.cursor()

    if request.method == 'GET':
        try:
            query = """SELECT "BK_ID", "BK_NAME", "AUTHOR_NAME", "BOOK_STATUS" FROM library WHERE "BOOK_STATUS" = 'Available'"""
            cursor.execute(query)
            books = cursor.fetchall()

            # Return the list of available books to the user
            return render_template('reserve.html', books=books)

        except Exception as e:
            # Log the error and return a message to the user
            app.logger.error(f"Error during database fetch: {e}")
            return "Error fetching books", 500

    if request.method == 'POST':
        try:
            book_id = request.form.get('book_id').strip()
            user_name = request.form.get('user_name').strip()
            contact = request.form.get('contact').strip()
            card_id = request.form.get('card_id').strip()  # Card ID to identify the user

            # Check if the user exists in the user_data database
            query = """SELECT "CARD_ID" FROM "user" WHERE "CARD_ID" = %s ;"""
            cursor.execute(query, (card_id,))
            user = cursor.fetchone()

            if user:
                # Check the count of books already reserved by the user
                query = """SELECT COUNT(*) FROM "library" WHERE "BOOK_STATUS" = 'Reserved' AND "CARD_ID" = %s ;"""
                cursor.execute(query, (card_id,))
                reserved_count = cursor.fetchone()[0]

                if reserved_count >= 2:
                    message = "Reservation not confirmed. You have already reserved 2 books, which is the maximum limit."
                else:
                    # Check if the book is available
                    query = """SELECT "BK_NAME", "BOOK_STATUS" FROM "library" WHERE "BK_ID" = %s ;"""
                    cursor.execute(query, (book_id,))
                    book = cursor.fetchone()

                    if book:
                        bk_name, bk_status = book
                        if bk_status == "Available":
                            # Update book status to "Reserved" and set the user CARD_ID
                            query = '''
                                    UPDATE "library" 
                                    SET "BOOK_STATUS" = 'Reserved', "CARD_ID" = %s
                                    WHERE "BK_ID" = %s;
                                    '''
                            cursor.execute(query, (int(card_id), book_id)) 
                            #cursor.execute(query)
                            db_connection.commit()
                            message = f"The book '{bk_name}' has been reserved successfully!"
                        else:
                            message = f"Sorry, the book '{bk_name}' is currently not available."
                    else:
                        message = "Book ID not found. Please check and try again."
            else:
                message = (
                    "Reservation not confirmed. You are not an existing member of BEN Library. "
                    "To become a member, borrow your first book directly from the library."
                )

        except Exception as e:
            # Log the error during POST and return a message to the user
            app.logger.error(f"Error during reservation process: {e}")
            message = "An error occurred while processing your reservation."

        # Close the database connection and cursor after handling POST request
        cursor.close()
        db_connection.close()

        return render_template('reservation_result.html', message=message)


if __name__ == '__main__':
    app.run(debug=True)