from flask import Flask, render_template, request, redirect, url_for
import google.generativeai as genai
from googlesearch import search
import psycopg2
import os

app = Flask(__name__)
database_password = os.getenv('DATABASE_PASSWORD')
api_key = os.getenv("API_KEY")

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.0-flash-exp")

def connect_to_library_db():
    return psycopg2.connect(
            host="aws-0-ap-southeast-1.pooler.supabase.com",  # E.g., localhost or an IP address
            database="postgres",                             # Your database name
            user="postgres.fxtisfulbcghgrljxblf", 
            port="6543",                                     # Your port
            password=f"{database_password}"                             # Your password
        )

def clean_response(response_text):
    cleaned_text = response_text.replace("*", "").replace("#", "").strip()
    return cleaned_text

def get_suggested_input(input_text):
    # Use AI to get a suggestion for corrected input
    response = model.generate_content(f"provide a correctly spelled version of this text: '{input_text}'."
                                       "if the text consists of random letters that is not meaningful in any language "
                                       "keep the text as it is, else give the corrected spelling version. "
                                       "Do not output anything other than the corrected version of the text."
    )

    return clean_response(response.text)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        search_type = request.form.get('search_type')
        search_input = request.form.get('search_input').strip()
        
        # Get AI suggestion for corrected input
        modified_input = get_suggested_input(search_input)

        if modified_input != search_input:
            # Inform the user if the AI suggests a correction
            return redirect(url_for('result', search_type=search_type, search_input=modified_input, original_input=search_input))
        else:
            # Proceed with the search if no modification
            return redirect(url_for('result', search_type=search_type, search_input=search_input))
    return render_template('index.html')

@app.route('/result')
def result():
    search_type = request.args.get('search_type')
    search_input = request.args.get('search_input')
    original_input = request.args.get('original_input', None)

    db_connection = connect_to_library_db()
    cursor = db_connection.cursor()

    # Prepare the input for searching by converting it to uppercase
    search_input_upper = search_input.upper()

    results = []
    cleaned_response = ""
    links = []

    if search_type == "Search by Author":
        query = """SELECT  "BK_NAME", "BK_ID", "BOOK_STATUS", "AUTHOR_NAME" FROM library WHERE levenshtein_less_equal("AUTHOR_NAME", %s, 2) <= 2 OR "AUTHOR_NAME" ILIKE %s ;"""
        cursor.execute(query, (f"{search_input_upper}",f"%{search_input_upper}%"))
        books = cursor.fetchall()

        if books:
            for book in books:
                bk_name, bk_id, bk_status, due_date = book
                results.append({
                    "bk_name": bk_name,
                    "bk_id": bk_id,
                    "bk_status": bk_status,
                    "due_date": due_date
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
        query = """SELECT "BK_NAME", "BK_ID", "BOOK_STATUS", "AUTHOR_NAME" FROM library WHERE levenshtein_less_equal("BK_NAME", %s, 2) <= 2 OR "BK_NAME" ILIKE %s """
        cursor.execute(query, (f"{search_input_upper}",f"%{search_input_upper}%"))
        books = cursor.fetchall()

        results = []
        if books:
            for book in books:
                bk_name, bk_id, bk_status, author_name = book
                output = {
                    "bk_name": bk_name,
                    "author_name": author_name,
                    "bk_id": bk_id,
                    "bk_status": bk_status,
                   
                }
                results.append(output)

        else:
            pass

        # Generate AI response about the book and the author regardless of book presence
        response = model.generate_content(
            f"Get a summary of the book '{search_input}' and information about the author. "
             "nothing other than the summary of the book and information about the author should be included in the output."
             "present the summary in a beautiful and readable format."
             "If the book name is invalid or not found include 'No summary found' in your response."
        )
        
        cleaned_response = clean_response(response.text)
        print(cleaned_response)

        

        if "No summary found" in cleaned_response:
            bk_links = []
            # Search online for additional details when no summary is found
            bk_links = list(search(f"Get summary of the book '{search_input_upper}'", num_results=5))
        
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

            # Log the fetched books for debugging
            app.logger.info(f"Books fetched: {books}")
            
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
                    query = """SELECT "BK_NAME", "BOOK_STATUS" FROM "library" WHERE "BK_ID" = %s;"""
                    cursor.execute(query, (book_id,))
                    book = cursor.fetchone()

                    if book:
                        bk_name, bk_status = book
                        if bk_status == "Available":
                            # Update book status to "Reserved" and set the user CARD_ID
                            query = """UPDATE "library" SET "BOOK_STATUS" = 'Reserved', "CARD_ID" = %s WHERE "BK_ID" = %s ;"""
                            cursor.execute(query, (card_id, book_id))

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

