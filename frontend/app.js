/*
 * IT Copilot frontend.
 *
 * Talks to the support-assistant API (POST /assistant/message).
 * The UI shows the triage tier and any ticket created, so the
 * full flow — classify, resolve or escalate, document — is visible
 * to whoever is testing it.
 */

const API_ENDPOINT = "/assistant/message";

const menuButton = document.getElementById("menuButton");
const closeSidebarButton = document.getElementById("closeSidebarButton");
const sidebarNewChatButton = document.getElementById("sidebarNewChatButton");
const newChatButton = document.getElementById("newChatButton");

const sidebar = document.getElementById("sidebar");
const sidebarOverlay = document.getElementById("sidebarOverlay");

const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const messages = document.getElementById("messages");

let conversationId = null;


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
    conversationId = null;
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
            <div class="welcome-icon">IT</div>
            <h1>How can I help?</h1>
            <p>
                Describe an IT problem and I'll help you
                troubleshoot it. Security issues reach a human
                immediately; everything else I try to resolve,
                and every conversation gets a documented ticket.
            </p>
            <div class="suggestions">
                <button class="suggestion">I think I clicked a phishing link</button>
                <button class="suggestion">I forgot my password</button>
                <button class="suggestion">My VPN won't connect</button>
            </div>
        </div>
    `;

    attachSuggestionHandlers();
}

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
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 140)}px`;
}

messageInput.addEventListener("input", resizeInput);

messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        chatForm.requestSubmit();
    }
});


/* ==========================================================
   Backend Request — support assistant API
   ========================================================== */

async function sendMessageToBackend(message) {
    try {
        const response = await fetch(API_ENDPOINT, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: message,
                conversation_id: conversationId,
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "The server returned an error.");
        }

        return await response.json();
    } catch (error) {
        console.error("Assistant error:", error);
        return { error: error.message };
    }
}


/* ==========================================================
   Messages
   ========================================================== */

function addUserMessage(text) {
    const message = document.createElement("div");
    message.className = "message user-message";
    message.innerHTML = `
        <div class="message-content">${escapeHtml(text)}</div>
    `;
    messages.appendChild(message);
    scrollToBottom();
}

function outcomeBadge(response) {
    if (response.suppressed) {
        return `<span class="badge badge-muted">IT is driving this conversation</span>`;
    }

    const badges = [];

    if (response.tier === "security") {
        badges.push(`<span class="badge badge-critical">Security escalation</span>`);
    } else if (response.escalated) {
        badges.push(`<span class="badge badge-warning">Escalated to IT</span>`);
    } else if (response.tier === "self_serve") {
        badges.push(`<span class="badge badge-ok">Self-serve</span>`);
    }

    if (response.ticket_id !== null && response.ticket_id !== undefined) {
        badges.push(`<span class="badge badge-muted">Ticket #${response.ticket_id}</span>`);
    }

    return badges.join(" ");
}

function addAssistantMessage(response) {
    const message = document.createElement("div");
    message.className = "message assistant-message";

    if (response.error) {
        message.innerHTML = `
            <div class="assistant-label">IT Copilot</div>
            <div class="message-content">
                <p>I couldn't reach the assistant server.</p>
                <p class="error-message">${escapeHtml(response.error)}</p>
            </div>
        `;
        messages.appendChild(message);
        scrollToBottom();
        return;
    }

    if (response.conversation_id !== undefined) {
        conversationId = response.conversation_id;
    }

    const badgeHtml = outcomeBadge(response);
    const body = response.reply
        ? formatResponse(response.reply)
        : "<p>No reply from the assistant.</p>";

    message.innerHTML = `
        <div class="assistant-label">IT Copilot</div>
        <div class="message-content">
            ${body}
            ${badgeHtml ? `<div class="badges">${badgeHtml}</div>` : ""}
        </div>
    `;

    messages.appendChild(message);
    scrollToBottom();
}


/* ==========================================================
   Markdown Rendering (compact)
   ========================================================== */

function formatResponse(text) {
    if (!text) {
        return "";
    }

    let escaped = escapeHtml(String(text))
        .replaceAll("\r\n", "\n")
        .replaceAll("\r", "\n");

    // Fenced code blocks -> placeholders.
    const codeBlocks = [];
    escaped = escaped.replace(/```(?:[^\n]*)\n?([\s\S]*?)```/g, (_, code) => {
        const index = codeBlocks.push(
            `<pre><code>${code.trim()}</code></pre>`
        ) - 1;
        return `@@CODE_BLOCK_${index}@@`;
    });

    const lines = escaped.split("\n");
    const output = [];
    let inList = null;

    const closeList = () => {
        if (inList) {
            output.push(`</${inList}>`);
            inList = null;
        }
    };

    for (const line of lines) {
        const trimmed = line.trim();

        if (!trimmed) {
            closeList();
            continue;
        }

        if (trimmed.includes("@@CODE_BLOCK_")) {
            closeList();
            output.push(trimmed);
            continue;
        }

        const heading = trimmed.match(/^(#{1,6})\s+(.*)$/);
        if (heading) {
            closeList();
            const level = heading[1].length;
            output.push(
                `<h${level}>${formatInline(heading[2])}</h${level}>`
            );
            continue;
        }

        const unordered = trimmed.match(/^[-*+]\s+(.*)$/);
        if (unordered) {
            if (inList !== "ul") {
                closeList();
                output.push("<ul>");
                inList = "ul";
            }
            output.push(`<li>${formatInline(unordered[1])}</li>`);
            continue;
        }

        const ordered = trimmed.match(/^\d+\.\s+(.*)$/);
        if (ordered) {
            if (inList !== "ol") {
                closeList();
                output.push("<ol>");
                inList = "ol";
            }
            output.push(`<li>${formatInline(ordered[1])}</li>`);
            continue;
        }

        closeList();
        output.push(`<p>${formatInline(trimmed)}</p>`);
    }

    closeList();

    let result = output.join("");

    codeBlocks.forEach((block, index) => {
        result = result.replace(`@@CODE_BLOCK_${index}@@`, block);
    });

    return result;
}

function formatInline(text) {
    let result = text;

    result = replaceBetweenMarkers(result, "`", "<code>", "</code>");
    result = replaceBetweenMarkers(result, "**", "<strong>", "</strong>");

    return result;
}

function replaceBetweenMarkers(text, marker, openingTag, closingTag) {
    let result = text;
    let searchPosition = 0;

    while (true) {
        const start = result.indexOf(marker, searchPosition);
        if (start === -1) {
            break;
        }

        const contentStart = start + marker.length;
        const end = result.indexOf(marker, contentStart);
        if (end === -1) {
            break;
        }

        const content = result.substring(contentStart, end);
        const replacement = openingTag + content + closingTag;

        result =
            result.substring(0, start) +
            replacement +
            result.substring(end + marker.length);

        searchPosition = start + replacement.length;
    }

    return result;
}


/* ==========================================================
   Form Submission
   ========================================================== */

chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const message = messageInput.value.trim();
    if (!message) {
        return;
    }

    messages.querySelector(".welcome")?.remove();

    addUserMessage(message);

    messageInput.value = "";
    messageInput.style.height = "auto";

    const response = await sendMessageToBackend(message);
    addAssistantMessage(response);
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


/* ==========================================================
   Init
   ========================================================== */

addWelcomeMessage();
