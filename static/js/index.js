document.addEventListener("DOMContentLoaded", function () {
    const toggle = document.getElementById("aiToggle");
    const statusBox = document.getElementById("toggleStatusBox");
    const slider = document.querySelector(".slider");

    function updateStatusBox(isChecked) {
        const isMobile = window.matchMedia("(max-width: 576px)").matches;

        if (isChecked) {
            statusBox.classList.remove("green-bg");
            statusBox.classList.add("blue-bg");
            statusBox.innerHTML = isMobile
                ? `<span class="line"><span class="highlight">Detailed Info Mode:</span> Slower, yet precise and</span><br>
                <span class="line">in-depth. Ideal for infamous books, deep insights</span><br>
                <span class="line">and comprehensive coverage.</span>`
                : `<span class="line"><span class="highlight">Detailed Info Mode:</span> Slower, yet precise and in-depth. Ideal for infamous     </span><br>
                <span class="line">books deep insights and comprehensive coverage.</span>`;
            slider.style.backgroundColor = "rgba(18, 133, 255, 0.544)";
        } else {
            statusBox.classList.remove("blue-bg");
            statusBox.classList.add("green-bg");
            statusBox.innerHTML = isMobile
                ? `<span class="line"><span class="highlight">Quick Info Mode:</span> Gives fast, clear summaries</span><br>
                <span class="line">for well-known books. May not cover obscure or</span><br>
                <span class="line">infamous titles because of limited data coverage.</span>`
                : `<span class="line"><span class="highlight">Quick Info Mode:</span> Gives fast, clear summaries for well-known books. But</span><br>
                <span class="line">may not cover obscure or infamous titles because of limited data coverage.</span>`;
            slider.style.backgroundColor = "rgba(72, 201, 120, 0.4)";
        }
    }

    // Initial setup
    updateStatusBox(toggle.checked);

    // Toggle event listener
    toggle.addEventListener("change", function () {
        updateStatusBox(this.checked);
    });

    // Update on screen resize to stay responsive
    window.addEventListener("resize", function () {
        updateStatusBox(toggle.checked);
    });
});


