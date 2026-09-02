const menuButton = document.getElementById("menuButton");
const closeSidebarButton = document.getElementById("closeSidebarButton");
const sidebarNewChatButton = document.getElementById("sidebarNewChatButton");
const newChatButton = document.getElementById("newChatButton");

const sidebar = document.getElementById("sidebar");
const sidebarOverlay = document.getElementById("sidebarOverlay");

const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const messages = document.getElementById("messages");


/* ==========================================================
   Sidebar
   ========================================================== */

function openSidebar() {
    sidebar.classList.add("open");
    sidebarOverlay.classList.add("visible");
}


function closeSidebar() {
    sidebar.classList.remove("open");
    sidebarOverlay.classList.remove("visible");
}


menuButton.addEventListener("click", openSidebar);

closeSidebarButton.addEventListener("click", closeSidebar);

sidebarOverlay.addEventListener("click", closeSidebar);


/* ==========================================================
   New Chat
   ========================================================== */

function startNewChat() {
    messages.innerHTML = "";

    addWelcomeMessage();

    messageInput.value = "";
    messageInput.style.height = "auto";

    closeSidebar();
    messageInput.focus();
}


sidebarNewChatButton.addEventListener("click", startNewChat);

newChatButton.addEventListener("click", startNewChat);


/* ==========================================================
   Welcome Screen
   ========================================================== */

function addWelcomeMessage() {
    messages.innerHTML = `
        <div class="welcome">
            <div class="welcome-icon">
                IT
            </div>

            <h1>
                How can I help?
            </h1>

            <p>
                Describe an IT problem and I'll help
                you troubleshoot it.
            </p>

            <div class="suggestions">

                <button class="suggestion">
                    My Windows PC is running slowly
                </button>

                <button class="suggestion">
                    Help me troubleshoot PowerShell
                </button>

                <button class="suggestion">
                    I can't connect to a Tailscale device
                </button>

            </div>
        </div>
    `;

    attachSuggestionHandlers();
}


/* ==========================================================
   Suggestions
   ========================================================== */

function attachSuggestionHandlers() {
    document.querySelectorAll(".suggestion").forEach((button) => {
        button.addEventListener("click", () => {
            messageInput.value = button.textContent.trim();

            resizeInput();

            messageInput.focus();
        });
    });
}


/* ==========================================================
   Message Input
   ========================================================== */

function resizeInput() {
    messageInput.style.height = "auto";

    messageInput.style.height =
        `${Math.min(messageInput.scrollHeight, 140)}px`;
}


messageInput.addEventListener("input", resizeInput);


messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();

        chatForm.requestSubmit();
    }
});


/* ==========================================================
   Add User Message
   ========================================================== */

function addUserMessage(text) {
    const message = document.createElement("div");

    message.className = "message user-message";

    message.innerHTML = `
        <div class="message-content">
            ${escapeHtml(text)}
        </div>
    `;

    messages.appendChild(message);

    scrollToBottom();
}


/* ==========================================================
   Add Assistant Message
   ========================================================== */

function addAssistantMessage() {
    const message = document.createElement("div");

    message.className = "message assistant-message";

    message.innerHTML = `
        <div class="assistant-label">
            IT Copilot
        </div>

        <div class="message-content">
            I can help troubleshoot that.

            <br><br>

            First, let's gather some information about
            the problem.

            <br><br>

            Try running:

            <pre><code>$PSVersionTable</code></pre>

            Then send me the output and I'll help
            determine the next step.

            <div class="sources">
                <div class="sources-title">
                    Sources
                </div>

                <div class="source">
                    PowerShell Knowledge Base
                </div>

                <div class="source">
                    Microsoft Knowledge Base
                </div>
            </div>
        </div>
    `;

    messages.appendChild(message);

    scrollToBottom();
}


/* ==========================================================
   Form Submission
   ========================================================== */

chatForm.addEventListener("submit", (event) => {
    event.preventDefault();

    const message = messageInput.value.trim();

    if (!message) {
        return;
    }

    messages.querySelector(".welcome")?.remove();

    addUserMessage(message);

    messageInput.value = "";
    messageInput.style.height = "auto";

    setTimeout(() => {
        addAssistantMessage();
    }, 500);
});


/* ==========================================================
   Helpers
   ========================================================== */

function scrollToBottom() {
    messages.scrollTo({
        top: messages.scrollHeight,
        behavior: "smooth",
    });
}


function escapeHtml(text) {
    const element = document.createElement("div");

    element.textContent = text;

    return element.innerHTML;
}