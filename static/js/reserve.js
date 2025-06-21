document.addEventListener('DOMContentLoaded', function () {
    const bookGrid = document.getElementById('bookGrid');
    const pagination = document.getElementById('pagination');
    const limit = 100;
    let currentPage = 1;

    init();

    function init() {
        fetchBooks(currentPage);
        setupReserveForm();
        setupSearchBox();
    }

    function fetchBooks(page = 1) {
        fetch(`/get_available_books?page=${page}&limit=${limit}`)
            .then(res => res.json())
            .then(data => {
                renderBooks(data.books);
                renderPagination(data.total, data.page);
            })
            .catch(err => console.error('Error fetching books:', err));
    }

    function renderBooks(books) {
        bookGrid.innerHTML = '';
        books.forEach(book => {
            const card = createBookCard(book);
            bookGrid.appendChild(card);
        });
        rebindAllEvents();
    }

    function renderPagination(totalItems, currentPage) {
        const totalPages = Math.ceil(totalItems / limit);
        pagination.innerHTML = '';

        const createPageButton = (text, page, isActive = false) => {
            const btn = document.createElement('button');
            btn.textContent = text;
            btn.className = 'btn btn-light mx-1' + (isActive ? ' active' : '');
            btn.disabled = (page === currentPage);
            btn.addEventListener('click', () => {
                fetchBooks(page);
                currentPage = page;
            });
            return btn;
        };

        if (currentPage > 1) pagination.appendChild(createPageButton('« Previous', currentPage - 1));

        for (let i = 1; i <= totalPages; i++) {
            if (i === 1 || i === totalPages || Math.abs(i - currentPage) <= 1) {
                pagination.appendChild(createPageButton(i, i, i === currentPage));
            } else if (i === currentPage - 2 || i === currentPage + 2) {
                const ellipsis = document.createElement('span');
                ellipsis.textContent = '...';
                ellipsis.className = 'mx-1';
                pagination.appendChild(ellipsis);
            }
        }

        if (currentPage < totalPages) pagination.appendChild(createPageButton('Next »', currentPage + 1));
    }

    function createBookCard(book) {
        const card = document.createElement('div');
        card.className = 'book-card fade-in';

        const content = document.createElement('div');
        content.className = 'content';
        content.innerHTML = `
            <h5>${book.bk_name}</h5>
            <p><strong>Author:</strong> ${book.author_name}</p>
            <p><strong>Book ID:</strong> ${book.bk_id}</p>
            <p><strong>Status:</strong> ${book.bk_status}</p>
            <p><strong>Shelf No.:</strong> ${book.shelf_no}</p>
            <p><strong>Rack No.:</strong> ${book.rack_no}</p>
            ${book.contributed === 'YES' ? `<span class="star-badge" data-contributor="${book.contributor}">⭐</span>` : ''}
        `;

        const buttonGroup = document.createElement('div');
        buttonGroup.className = 'button-group';
        buttonGroup.innerHTML = `
            <form class="info-form">
                <input type="hidden" name="bk_name" value="${book.bk_name}">
                <input type="hidden" name="author_name" value="${book.author_name}">
                <button type="submit" class="btn btn-primary book-info-btn">
                    Generate Book Info
                    <span class="spinner-border spinner-border-sm ms-2 d-none" role="status" aria-hidden="true"></span>
                </button>
            </form>
            <button type="button" class="btn btn-primary reserve-btn"
                data-book-id="${book.bk_id}"
                data-book-name="${book.bk_name}">Reserve</button>
        `;

        card.appendChild(content);
        card.appendChild(buttonGroup);
        return card;
    }

    function rebindAllEvents() {
        bindReserveButtons();
        bindInfoForms();
    }

    function bindReserveButtons() {
        document.querySelectorAll('.reserve-btn').forEach(btn => {
            btn.addEventListener('click', function () {
                document.getElementById('bookIdInput').value = this.dataset.bookId;
                document.getElementById('bookNameDisplay').textContent = this.dataset.bookName;
                document.getElementById('reserveMessage').textContent = '';
                document.getElementById('cardIdInput').value = '';
                $('#reserveModal').modal('show');
            });
        });
    }

    function bindInfoForms() {
        document.querySelectorAll('.info-form').forEach(form => {
            form.addEventListener('submit', function (e) {
                e.preventDefault();

                const submitButton = form.querySelector('button[type="submit"]');
                const spinner = submitButton.querySelector('.custom-spinner') || createSpinner(submitButton);

                spinner.classList.remove('d-none');
                submitButton.disabled = true;

                const formData = new FormData(form);

                fetch('/get_info', {
                    method: 'POST',
                    body: formData
                })
                    .then(response => response.text())
                    .then(message => {
                        spinner.classList.add('d-none');
                        submitButton.disabled = false;

                        const bookCard = form.closest('.book-card');
                        if (bookCard) {
                            showPopupMessage(bookCard, message);
                        } else {
                            console.error('Could not find .book-card to show popup');
                        }
                    })
                    .catch(error => {
                        spinner.classList.add('d-none');
                        submitButton.disabled = false;
                        alert('Error: ' + error);
                    });
            });
        });
    }



    function bindFormSubmit(form) {
        const submitButton = form.querySelector('button[type="submit"]');
        const spinner = submitButton.querySelector('.custom-spinner') || createSpinner(submitButton);

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            spinner.classList.remove('d-none');
            submitButton.disabled = true;

            const formData = new FormData(form);

            fetch('/get_info', {
                method: 'POST',
                body: formData
            })
                .then(response => response.text())
                .then(message => {
                    spinner.classList.add('d-none');
                    submitButton.disabled = false;
                    showPopupMessage(form.closest('.book-card'), message);
                })
                .catch(error => {
                    spinner.classList.add('d-none');
                    submitButton.disabled = false;
                    alert('Error: ' + error);
                });
        });
    }

    function createSpinner(button) {
        const spinner = document.createElement('span');
        spinner.className = 'custom-spinner d-none';
        spinner.style.width = '14px';
        spinner.style.height = '14px';
        spinner.style.border = '2px solid white';
        spinner.style.borderTop = '2px solid transparent';
        spinner.style.borderRadius = '50%';
        spinner.style.display = 'inline-block';
        spinner.style.marginLeft = '8px';
        spinner.style.animation = 'spin 0.6s linear infinite';
        button.appendChild(spinner);
        return spinner;
    }

    function showPopupMessage(card, message) {
        const originalContent = card.innerHTML;
        card.dataset.originalContent = originalContent;
        card.innerHTML = '';

        const popup = document.createElement('div');
        popup.style = 'position:absolute;top:0;left:0;width:100%;height:100%;background:rgba(29,31,31,0.9);border:1px solid #ccc;box-shadow:0 2px 8px rgba(0,0,0,0.2);z-index:10;display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:4px;overflow:hidden;padding:10px';

        const closeButton = document.createElement('span');
        closeButton.innerHTML = '&times;';
        closeButton.style = 'position:absolute;top:10px;right:18px;cursor:pointer;font-size:24px;font-weight:bold;color:#fff';
        closeButton.addEventListener('click', function () {
            card.innerHTML = card.dataset.originalContent;
            rebindAllEvents(); // This rebinds events to the newly restored elements
            bindInfoForms();   // Ensure forms get re-bound as well
        });

        const messageContent = document.createElement('div');
        messageContent.className = 'popup-message-content';
        messageContent.style = 'white-space:pre-wrap;max-height:100%;overflow-y:auto;width:100%;font-size:14px;line-height:1.5;text-align:left;color:#fff;margin:0;padding:0 10px;font-family:Fira Code, monospace';
        messageContent.textContent = message;

        messageContent.style.scrollbarWidth = 'thin';
        messageContent.style.scrollbarColor = '#888 #1d1f1f';

        if (!document.getElementById('popup-scroll-style')) {
            const style = document.createElement('style');
            style.id = 'popup-scroll-style';
            style.textContent = `
                .popup-message-content::-webkit-scrollbar { width: 6px; }
                .popup-message-content::-webkit-scrollbar-track { background: #1d1f1f; }
                .popup-message-content::-webkit-scrollbar-thumb { background-color: #888; border-radius: 3px; }
                .popup-message-content::-webkit-scrollbar-button { display: none; }
                .popup-message-content::-webkit-scrollbar-thumb:hover { background: #555; }
            `;
            document.head.appendChild(style);
        }

        popup.appendChild(closeButton);
        popup.appendChild(messageContent);
        card.style.position = 'relative';
        card.appendChild(popup);
    }

    function setupReserveForm() {
        const form = document.getElementById('reserveForm');
        if (!form) return;

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            const formData = new FormData(form);
            const reserveMessage = document.getElementById('reserveMessage');

            fetch('/api/reserve', {
                method: 'POST',
                body: formData
            })
                .then(response => response.text())
                .then(message => {
                    $('#reserveModal').modal('hide');
                    alert(message);
                    fetchBooks(currentPage);
                })
                .catch(error => {
                    reserveMessage.textContent = 'Error reserving the book. Please try again.';
                    console.error(error);
                });
        });
    }
    function setupSearchBox() {
        const searchBox = document.getElementById('search-box');
        let debounceTimer;

        searchBox.addEventListener('input', () => {
            const query = searchBox.value.trim();
            clearTimeout(debounceTimer);

            debounceTimer = setTimeout(() => {
                if (query === '') {
                    fetchBooks(currentPage); // revert to paginated list
                    pagination.style.display = 'flex';
                } else {
                    performSearch(query);
                }
            }, 250);
        });
    }

    function performSearch(query) {
        bookGrid.innerHTML = '<p class="text-center">Searching...</p>';
        fetch(`/search_books?query=${encodeURIComponent(query)}`)
            .then(res => res.json())
            .then(data => {
                renderBooks(data.books);
                pagination.style.display = 'none';
            })
            .catch(err => {
                console.error('Error during search:', err);
                bookGrid.innerHTML = '<p class="text-danger text-center">Error while searching.</p>';
            });
    }


});