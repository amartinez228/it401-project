document.addEventListener("DOMContentLoaded", () => {
    const storage = {
        read(key) {
            try {
                return JSON.parse(window.localStorage.getItem(key)) || {};
            } catch (_error) {
                return {};
            }
        },
        write(key, value) {
            try {
                window.localStorage.setItem(key, JSON.stringify(value));
            } catch (_error) {
                // The page still works when browser storage is unavailable.
            }
        },
    };

    const toast = document.querySelector(".toast");
    let toastTimer;
    const showToast = (message) => {
        if (!toast) return;
        toast.textContent = message;
        toast.classList.add("visible");
        window.clearTimeout(toastTimer);
        toastTimer = window.setTimeout(() => toast.classList.remove("visible"), 2200);
    };

    const navToggle = document.querySelector(".nav-toggle");
    const siteNav = document.querySelector(".site-nav");
    if (navToggle && siteNav) {
        navToggle.addEventListener("click", () => {
            const isOpen = siteNav.classList.toggle("open");
            navToggle.setAttribute("aria-expanded", String(isOpen));
        });
    }

    const passwordToggle = document.querySelector(".password-toggle");
    if (passwordToggle) {
        const password = document.getElementById(passwordToggle.getAttribute("aria-controls"));
        passwordToggle.addEventListener("click", () => {
            const shouldShow = password.type === "password";
            password.type = shouldShow ? "text" : "password";
            passwordToggle.textContent = shouldShow ? "Hide" : "Show";
        });
    }

    const ratings = storage.read("betterboxd-ratings");
    document.querySelectorAll("[data-rating-key]").forEach((ratingGroup) => {
        const key = ratingGroup.dataset.ratingKey;
        const buttons = [...ratingGroup.querySelectorAll("[data-value]")];
        const output = ratingGroup.querySelector("output");

        const paintStars = (value, className = "selected") => {
            buttons.forEach((button) => {
                button.classList.toggle(className, Number(button.dataset.value) <= value);
            });
        };

        const savedRating = Number(ratings[key] || 0);
        if (savedRating) {
            paintStars(savedRating);
            output.textContent = `${savedRating}/5`;
        }

        buttons.forEach((button) => {
            const value = Number(button.dataset.value);
            button.addEventListener("mouseenter", () => paintStars(value, "hovered"));
            button.addEventListener("focus", () => paintStars(value, "hovered"));
            button.addEventListener("mouseleave", () => buttons.forEach((star) => star.classList.remove("hovered")));
            button.addEventListener("blur", () => buttons.forEach((star) => star.classList.remove("hovered")));
            button.addEventListener("click", () => {
                ratings[key] = value;
                storage.write("betterboxd-ratings", ratings);
                buttons.forEach((star) => star.classList.remove("selected"));
                paintStars(value);
                output.textContent = `${value}/5`;
                showToast(`Rating saved: ${value} out of 5 stars`);
            });
        });
    });

    const follows = storage.read("betterboxd-follows");
    document.querySelectorAll("[data-follow-key]").forEach((button) => {
        const key = button.dataset.followKey;
        const unfollowedText = button.textContent.trim();
        const followedText = button.dataset.followedText || "✓ Following";

        const displayState = () => {
            const isFollowing = Boolean(follows[key]);
            button.classList.toggle("following", isFollowing);
            button.setAttribute("aria-pressed", String(isFollowing));
            button.textContent = isFollowing ? followedText : unfollowedText;
        };

        displayState();
        button.addEventListener("click", () => {
            follows[key] = !follows[key];
            storage.write("betterboxd-follows", follows);
            displayState();
            showToast(follows[key] ? "Added to your follows" : "Removed from your follows");
        });
    });

    const flashMessages = document.querySelectorAll(".flash-message");
    if (flashMessages.length) {
        window.setTimeout(() => {
            flashMessages.forEach((message) => {
                message.style.opacity = "0";
                message.style.transition = "opacity 300ms ease";
            });
        }, 4200);
    }
});
