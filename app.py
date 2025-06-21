from flask import Flask, render_template, request, redirect, url_for, jsonify
import google.generativeai as genai
from googlesearch import search
import psycopg2
import psycopg2.extras
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
    storage_uri=f"redis://default:{redis_pass}@redis-11307.c301.ap-south-1-1.ec2.redns.redis-cloud.com:11307"
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

@app.route('/', methods=['GET', 'POST'])
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
        ai_model = 'sw_value' in request.form
        return redirect(url_for('result', search_type=search_type, search_input=search_input, ai_model=ai_model))
    return render_template('index.html')

@app.route('/result')
@limiter.limit("10 per minute") 
def result():
    search_type = request.args.get('search_type')
    search_input = request.args.get('search_input')
    fastmodel = request.args.get('ai_model') == 'False' # it was str so converted it to bool

    genai.configure(api_key=api_key)
    if fastmodel:
        model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-06-17")
    else:
        model = genai.GenerativeModel("gemini-2.5-flash")
        
    db_connection = connect_to_library_db()
    cursor = db_connection.cursor()


    search_input_upper = search_input.upper()
    results = []
    cleaned_response = ""
    links = []

    if search_type == "Search by Author":
        query = """
            SELECT "BK_NAME", "BK_ID", "BOOK_STATUS", "AUTHOR_NAME", "CONTRIBUTED", "IF_YES_NAME"
            FROM library
            WHERE similarity("AUTHOR_NAME", %s) > 0.3
            OR "AUTHOR_NAME" ILIKE %s
            ORDER BY similarity("AUTHOR_NAME", %s) DESC
            LIMIT 10;
        """
        cursor.execute(query, (search_input_upper, f"%{search_input_upper}%", search_input_upper))
        books = cursor.fetchall()

        if books:
            for book in books:
                bk_name, bk_id, bk_status, author_name, contributed, contributor= book
                results.append({
                    "bk_name": bk_name,
                    "bk_id": bk_id,
                    "bk_status": bk_status,
                    "author_name": author_name,
                    "contributed": contributed,
                    "contributor": contributor
                })

        else:
            pass
        # Handle the case where no books are found
        response = model.generate_content(
            f"""Get details about {search_input} and books by the author/publisher.
                Do not use '**' and '##' in your response because it will not work, arrange you response in a pretty manner. 
                Only include the details, do not include any talks or questions,
                There is a possiblity for spelling mistake in the name so do check it, 
                If {search_input} is invalid or not known, include 'No Information found' in your response."""

        )
        cleaned_response = response.text

        if "No Information found" in cleaned_response:
            # If AI says no results, perform a web search
            links = list(search(f"Details about the author '{search_input_upper}'", num_results=3))
            cleaned_response = f"No results found for the author '{search_input}'. Refer to the related links below."

        # return a response for Search by Author
        return render_template(
            'result.html',
            results=results,
            generated_info=cleaned_response,
            search_input=search_input,
            links=links
        )


    elif search_type == "Search by Book":
        query = """
            SELECT "BK_NAME", "BK_ID", "BOOK_STATUS", "AUTHOR_NAME", "CONTRIBUTED", "IF_YES_NAME"
            FROM library
            WHERE similarity("BK_NAME", %s) > 0.3
            OR "BK_NAME" ILIKE %s
            ORDER BY similarity("BK_NAME", %s) DESC
            LIMIT 10;
        """
        cursor.execute(query, (search_input_upper, f"%{search_input_upper}%", search_input_upper))
        books = cursor.fetchall()

        results = []
        if books:
            for book in books:
                bk_name, bk_id, bk_status, author_name, contributed, contributor= book
                results.append({
                    "bk_name": bk_name,
                    "bk_id": bk_id,
                    "bk_status": bk_status,
                    "author_name": author_name,
                    "contributed": contributed,
                    "contributor": contributor
                })

        response = model.generate_content(
                f"""
                    You are a helpful assistant for a library app.

                    The user has searched for a book titled: "{search_input}".
                    There is a possibility of spelling mistake in the book name do consider it.

                    Your task is to:
                    1. Determine what kind of book it is — for example, is it a novel, story, biography, textbook, dictionary, reference manual, or something else?
                    2. If the book is a **story-based work** (like a novel, short story collection, or biography), generate a **summary** of its content point wise and add it under the section **Book Summary**.
                    3. If the book is **non-narrative**, like a **dictionary**, **encyclopedia**, **manual**, or **technical reference**, do **not** generate a summary. Instead, briefly **describe what the book is about**.
                    4. If the author's name is known, add detail information in a separate section titled **About the Author**.
                    5. If other informations like **Genre**, **Language**, **Setting**, **Pages**, **Publisher**, **Publication Date** are known. add it to a seperate section **Other details**.
                    5. If the book is not valid or no information is found, reply with **"No summary found."**

                    **Important:** Do not include phrases like "Okay, I'm ready", "Here's how I will respond", or any introduction. Just output the clean result starting with the relevant section title.
                    
                    Use clear formatting like this:
                    [Title (In most cases it should be the name of the book)]

                    **Book Summary**
                    [response here]

                    **About the Author**
                    [optional section here]

                    **Other details:**
                    [response here]

                    Be concise, fact-based, and avoid making up details. If the title sounds generic or non-narrative, do not treat it as a story.
                """
        )


        if "No summary found" in response.text:
            links = []
            # Search online for additional details when no summary is found
            bk_links = list(search(f"Get summary of the novel '{search_input_upper}'", num_results=3))

            # Update response to include a note about related links
            cleaned_response = f"No summary found for the book '{search_input}'. Refer to the related links below for more information."
        else:
            cleaned_response = response.text.replace('***', '').replace('**', '').replace('##', '').replace('#', '')

        return render_template(
            'result.html',
            results=results,  # Pass any database results or an empty list if none
            generated_info=cleaned_response, 
            search_input=search_input,
            links=links  # Pass related links
        )

    cursor.close()
    db_connection.close()


@app.route('/contribute', methods=['GET', 'POST'])
def contribution():
    if request.method == 'POST':
        book_name = request.form.get('book_name', '').strip()
        author_name = request.form.get('author_name', '').strip()
        card_id = request.form.get('card_id', '').strip()
        contributer_name = request.form.get('contributer_name', '').strip()

        db_connection = connect_to_library_db()
        cursor = db_connection.cursor()

        try:
            # Check if the card ID exists in the 'user' table
            cursor.execute("""SELECT "CARD_ID" FROM "user" WHERE "CARD_ID" = %s;""", (card_id,))
            user = cursor.fetchone()

            if not user:
                return jsonify({'status': 'error', 'message': "Error: Your card ID is not present in the database."})

            # Insert the book details into the 'contributed' table
            insert_query = """
                INSERT INTO "contributed" ("book", "author", "contributed_by", "contributer_name", "DATE")
                VALUES (%s, %s, %s, %s, CURRENT_DATE);
            """
            cursor.execute(insert_query, (book_name, author_name, card_id, contributer_name))
            db_connection.commit()

            message = (
                f"Thank you for contributing '{book_name}' by {author_name}! "
                "Once the book is received by the librarian, it will be added to the library's collection. "
                "Your name will be displayed near book."
            )

            return jsonify({'status': 'success', 'message': message})

        except Exception as e:
            app.logger.error(f"Error during contribution: {e}")
            return jsonify({'status': 'error', 'message': "An error occurred while processing your contribution."})

        finally:
            cursor.close()
            db_connection.close()

    return render_template('contribute.html')

@app.route('/get_available_books')
def get_available_books():
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 100))
        offset = (page - 1) * limit

        db_connection = connect_to_library_db()
        cursor = db_connection.cursor()

        count_query = 'SELECT COUNT(*) FROM library WHERE "BOOK_STATUS" = %s;'
        cursor.execute(count_query, ('Available',))
        total = cursor.fetchone()[0]

        query = '''
            SELECT "BK_ID", "BK_NAME", "AUTHOR_NAME", "BOOK_STATUS", "SHELF_NO", "RACK_NO", "CONTRIBUTED", "IF_YES_NAME"
            FROM library WHERE "BOOK_STATUS" = %s
            ORDER BY "BK_ID"
            LIMIT %s OFFSET %s;
        '''
        cursor.execute(query, ('Available', limit, offset))
        books = cursor.fetchall()

        results = []
        for book in books:
            bk_id, bk_name, author_name, bk_status, shelf_no, rack_no, contributed, contributor = book
            results.append({
                "bk_id": bk_id,
                "bk_name": bk_name,
                "author_name": author_name,
                "bk_status": bk_status,
                "shelf_no": shelf_no,
                "rack_no": rack_no,
                "contributed": contributed,
                "contributor": contributor
            })

        return jsonify({
            "books": results,
            "total": total,
            "page": page,
            "limit": limit
        })

    finally:
        cursor.close()
        db_connection.close()

@app.route('/get_info', methods=['POST'])
def get_info():
    book = request.form.get('bk_name')
    author = request.form.get('author_name')

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash-lite-preview-06-17")
    response = model.generate_content(
        f"""Provide detailed and structured information about the book "{book}" by {author}. 
            Do not write any introduction or conclusion. Use bullet points under each heading. 
            If any section is not applicable to the book, skip it without mentioning that it's skipped. 
            Follow this exact format:

            Title: [Book Title]
            Author: [Author Name]
            Type: [e.g., Novel, Biography, Academic, Technical, etc.]
            Genre: [e.g., Fiction, Non-Fiction, Mystery, etc.]

            Description: [Brief and informative description of the book]

            [Main Topics / Themes]:
            - [point 1]
            - [point 2]

            [Key Points / Learnings]:
            - [point 1]
            - [point 2]

            Author Background:
            - [point about the author's background]
            - [point about notable achievements]

            Only provide these headings and bullet points. Do not add any other text or explanation. """
    )

    message = response.text.replace('***', '').replace('**', '')
    return message

@app.route('/api/reserve', methods=['POST'])
def reserve():
    db_connection = connect_to_library_db()
    cursor = db_connection.cursor()
    try:
        book_id = request.form.get('book_id', '').strip()
        card_id = request.form.get('card_id', '').strip()

        if not book_id or not card_id:
            return "Invalid request. Missing book ID or card ID.", 400

        cursor = db_connection.cursor()

        # Check if user exists
        query = """SELECT "CARD_ID" FROM "user" WHERE "CARD_ID" = %s ;"""
        cursor.execute(query, (card_id,))
        user = cursor.fetchone()

        if user:
            # Check reservation count
            query = """SELECT COUNT(*) FROM "library" WHERE "BOOK_STATUS" = 'Reserved' AND "CARD_ID" = %s ;"""
            cursor.execute(query, (card_id,))
            reserved_count = cursor.fetchone()[0]

            if reserved_count >= 1:
                message = "Reservation not confirmed. You have already reserved 1 book, which is the maximum limit."
            else:
                # Check book availability
                query = """SELECT "BK_NAME", "BOOK_STATUS" FROM "library" WHERE "BK_ID" = %s ;"""
                cursor.execute(query, (book_id,))
                book = cursor.fetchone()

                if book:
                    bk_name, bk_status = book
                    if bk_status == "Available":
                        # Update reservation
                        update_query = '''
                            UPDATE "library" 
                            SET "BOOK_STATUS" = 'Reserved', "CARD_ID" = %s
                            WHERE "BK_ID" = %s;
                        '''
                        cursor.execute(update_query, (int(card_id), book_id))
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

        return message

    except Exception as e:
        return f"An error occurred during reservation: {str(e)}", 500
    finally:
        if cursor:
            cursor.close()
        if db_connection:
            db_connection.close()

@app.route('/search_books')
def search_books():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({'books': []})
    conn = connect_to_library_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    sql = '''
        SELECT * FROM "library"
        WHERE ("BK_NAME" ILIKE %s OR "AUTHOR_NAME" ILIKE %s)
        AND "BOOK_STATUS" = 'Available'
        LIMIT 100
    '''
    cursor.execute(sql, (f'%{query}%', f'%{query}%'))
    rows = cursor.fetchall()
    cursor.close()

    books = [{
        'bk_id': row['BK_ID'],
        'bk_name': row['BK_NAME'],
        'author_name': row['AUTHOR_NAME'],
        'bk_status': row['BOOK_STATUS'],
        'shelf_no': row['SHELF_NO'],
        'rack_no': row['RACK_NO'],
        'contributed': row.get('CONTRIBUTED', ''),
        'contributor': row.get('IF_YES_NAME', '')
    } for row in rows]

    return jsonify({'books': books})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)