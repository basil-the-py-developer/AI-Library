from flask import Flask, render_template, request, redirect, url_for
import mysql.connector
import google.generativeai as genai
from googlesearch import search
import os

app = Flask(__name__)

api_key = os.getenv("API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-1.5-flash")

def connect_to_library_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="helon@123",
        database="library_db"
    )

def connect_to_():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="helon@123",
        database="library_db"
    )

def clean_response(response_text):
    cleaned_text = response_text.replace("*", "").replace("#", "").strip()
    return cleaned_text

def get_suggested_input(input_text):
    # Use AI to get a suggestion for corrected input
    response = model.generate_content(f"Suggest a correctly spelled version of this text: {input_text}")

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
        query = "SELECT BK_NAME, BK_ID, BK_STATUS, DUE_DATE FROM Library WHERE UPPER(AUTHOR_NAME) LIKE %s"
        cursor.execute(query, (f"%{search_input_upper}%",))
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
            cleaned_response = f"Books by author '{search_input}' are available."
        else:
            # Handle the case where no books are found
            response = model.generate_content(
                f"Get details about the author {search_input} and the books. If no details are found, just say 'No results.'"
            )
            cleaned_response = clean_response(response.text)

            if cleaned_response.lower() == "no results.":
                # If AI says no results, perform a web search
                links = list(search(f"get details about the author {search_input_upper}", tld="com", num=10, stop=10, pause=2))
                cleaned_response = "No results found. Refer to the related links below."

        # Ensure we always return a response for "Search by Author"
        return render_template(
            'result.html',
            results=results,
            generated_info=cleaned_response,
            search_input=search_input,
            original_input=original_input,
            links=links
        )


    elif search_type == "Search by Book":
        query = "SELECT BK_NAME, BK_ID, BK_STATUS, AUTHOR_NAME, DUE_DATE FROM Library WHERE UPPER(BK_NAME) LIKE %s"
        cursor.execute(query, (f"%{search_input_upper}%",))
        books = cursor.fetchall()

        results = []
        if books:
            for book in books:
                bk_name, bk_id, bk_status, author_name, due_date = book
                output = {
                    "bk_name": bk_name,
                    "author_name": author_name,
                    "bk_id": bk_id,
                    "bk_status": bk_status,
                    "due_date": due_date
                }
                results.append(output)

            book_names = [book[0] for book in books]
        else:
            book_names = []
            if book_names== []:
                book_names=search_input

        # Generate AI response about the book and the author regardless of book presence
        response = model.generate_content(
            f"Get a summary of the book '{search_input}'  and information about the author. "
            "If a summary is not available, get the output as 'No summary found'."
        )
        
        cleaned_response = clean_response(response.text)

        

        if "No summary found" in cleaned_response:
            bk_links = []
            # Search online for additional details when no summary is found
            for i in search(f"Get summary of  the book '{search_input.upper()}'", tld="com", num=10, stop=10, pause=2):
                bk_links.append(i)

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

def connect_to_library_db():
    """Connect to the library database."""
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="helon@123",
        database="library_db"
    )

def connect_to_user_db():
    """Connect to the user_data database."""
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="helon@123",
        database="user_data"
    )

@app.route('/reserve', methods=['GET', 'POST'])
def reserve_book():
    if request.method == 'GET':
        db_connection = connect_to_library_db()
        cursor = db_connection.cursor()

        # Fetch available books (books with BK_STATUS = "Available")
        query = "SELECT BK_ID, BK_NAME, AUTHOR_NAME, BK_STATUS FROM Library WHERE BK_STATUS = 'Available'"
        cursor.execute(query)
        books = cursor.fetchall()

        cursor.close()
        db_connection.close()

        return render_template('reserve.html', books=books)

    if request.method == 'POST':
        book_id = request.form.get('book_id').strip()
        user_name = request.form.get('user_name').strip()
        contact = request.form.get('contact').strip()
        card_id = request.form.get('card_id').strip()  # Card ID to identify the user

        # Connect to user_data database to check for membership
        user_db_connection = connect_to_user_db()
        user_cursor = user_db_connection.cursor()

        # Check if the user exists in the user_data database
        user_query = "SELECT CARD_ID FROM user WHERE CARD_ID = %s"  # Assuming the table is 'user'
        user_cursor.execute(user_query, (card_id,))
        user = user_cursor.fetchone()

        if user:
            # User exists, now check the library database
            library_db_connection = connect_to_library_db()
            library_cursor = library_db_connection.cursor()

            # Check the count of books already reserved by the user
            count_query = "SELECT COUNT(*) FROM Library WHERE BK_STATUS = 'Reserved' AND CARD_ID = %s"
            library_cursor.execute(count_query, (card_id,))
            reserved_count = library_cursor.fetchone()[0]

            if reserved_count >= 2:
                message = "Reservation not confirmed. You have already reserved 2 books, which is the maximum limit."

            else:
                # Check if the book is available
                book_query = "SELECT BK_NAME, BK_STATUS FROM Library WHERE BK_ID = %s"
                library_cursor.execute(book_query, (book_id,))
                book = library_cursor.fetchone()

                if book:
                    bk_name, bk_status = book
                    if bk_status == "Available":
                        # Update book status to "Reserved" and set the user CARD_ID
                        update_query = "UPDATE Library SET BK_STATUS = 'Reserved', CARD_ID = %s WHERE BK_ID = %s"
                        library_cursor.execute(update_query, (card_id, book_id))
                        library_db_connection.commit()

                        message = f"The book '{bk_name}' has been reserved successfully!"
                    else:
                        message = f"Sorry, the book '{bk_name}' is currently not available."
                else:
                    message = "Book ID not found. Please check and try again."

            library_cursor.close()
            library_db_connection.close()
        else:
            message = (
                "Reservation not confirmed. You are not an existing member of BEN Library. "
                "To become a member, borrow your first book directly from the library."
            )

        user_cursor.close()
        user_db_connection.close()

        return render_template('reservation_result.html', message=message)


if __name__ == '__main__':
    app.run(debug=True)
