/* ============================================================
   FlowMind AI - Google Sign-In Experience
   Single-path auth using Google Identity Services (OIDC / OAuth 2.0)
   ============================================================ */

const GOOGLE_CLIENT_ID = document
    .querySelector('meta[name="google-signin-client_id"]')
    ?.getAttribute("content")
    ?.trim();

function setStoredSession({ token, user, profile = null }) {
    localStorage.setItem("flowmind_token", token);
    localStorage.setItem("flowmind_user", user);
    localStorage.setItem("flowmind_auth_provider", "google");
    if (profile) {
        localStorage.setItem("flowmind_user_profile", JSON.stringify(profile));
    } else {
        localStorage.removeItem("flowmind_user_profile");
    }
}

function clearStoredSession() {
    localStorage.removeItem("flowmind_token");
    localStorage.removeItem("flowmind_user");
    localStorage.removeItem("flowmind_auth_provider");
    localStorage.removeItem("flowmind_user_profile");
}

function updateGoogleStatus(message, type = "neutral") {
    const statusEl = document.getElementById("googleSigninStatus");
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.className = `google-signin-status ${type}`;
}

function decodeJwtPayload(token) {
    try {
        const [, payload] = token.split(".");
        const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
        const json = decodeURIComponent(
            atob(base64)
                .split("")
                .map((char) => `%${char.charCodeAt(0).toString(16).padStart(2, "0")}`)
                .join("")
        );
        return JSON.parse(json);
    } catch (error) {
        console.warn("Could not decode Google credential payload", error);
        return null;
    }
}

function redirectToApp() {
    window.location.href = "index.html";
}

function handleGoogleCredentialResponse(response) {
    if (!response?.credential) {
        updateGoogleStatus("Google sign-in failed. Please try again.", "error");
        return;
    }

    const payload = decodeJwtPayload(response.credential);
    if (!payload?.email) {
        updateGoogleStatus("Google returned an invalid identity token.", "error");
        return;
    }

    const displayName = payload.name || payload.given_name || payload.email;
    const profile = {
        name: displayName,
        email: payload.email,
        picture: payload.picture || "",
    };

    setStoredSession({
        token: response.credential,
        user: displayName,
        profile,
    });

    updateGoogleStatus(`Signed in as ${displayName}. Redirecting...`, "success");
    setTimeout(redirectToApp, 500);
}

function handleDemoLogin() {
    setStoredSession({
        token: "demo_bypass_token",
        user: "Demo Guest",
        profile: {
            name: "Demo Guest",
            email: "demo@flowmind.ai",
            picture: ""
        }
    });
    updateGoogleStatus("Signing in as Guest. Redirecting...", "success");
    setTimeout(redirectToApp, 500);
}

function initializeGoogleSignIn() {
    if (!window.google?.accounts?.id) {
        updateGoogleStatus("Google Identity Services could not be loaded.", "error");
        return;
    }

    if (!GOOGLE_CLIENT_ID || GOOGLE_CLIENT_ID.includes("YOUR_GOOGLE_CLIENT_ID")) {
        updateGoogleStatus(
            "Add your Google Web Client ID in login.html to enable live OIDC sign-in.",
            "warning"
        );
        return;
    }

    const slot = document.getElementById("googleSigninSlot");
    if (!slot) return;

    window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleGoogleCredentialResponse,
        auto_select: false,
        cancel_on_tap_outside: true,
        context: "signin",
    });

    window.google.accounts.id.renderButton(slot, {
        type: "standard",
        theme: "filled_black",
        size: "large",
        text: "continue_with",
        shape: "pill",
        width: 360,
        logo_alignment: "left",
    });

    window.google.accounts.id.prompt((notification) => {
        if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
            updateGoogleStatus("Google sign-in is ready. Use the button above to continue.", "neutral");
        }
    });

    updateGoogleStatus("Google sign-in is ready.", "success");
}

function initGrid() {
    const canvas = document.getElementById("gridCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        draw();
    }

    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.strokeStyle = "rgba(255, 255, 255, 0.16)";
        ctx.lineWidth = 0.5;
        const gap = 64;

        for (let x = 0; x < canvas.width; x += gap) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, canvas.height);
            ctx.stroke();
        }

        for (let y = 0; y < canvas.height; y += gap) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(canvas.width, y);
            ctx.stroke();
        }
    }

    resize();
    window.addEventListener("resize", resize);
}

document.addEventListener("DOMContentLoaded", () => {
    const token = localStorage.getItem("flowmind_token");
    if (token) {
        redirectToApp();
        return;
    }

    clearStoredSession();
    initGrid();

    if (window.google?.accounts?.id) {
        initializeGoogleSignIn();
    } else {
        updateGoogleStatus("Loading Google sign-in...", "neutral");
        window.addEventListener("load", () => {
            setTimeout(initializeGoogleSignIn, 200);
        });
    }
});