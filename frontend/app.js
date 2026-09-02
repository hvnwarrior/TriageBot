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
   Backend Request
   ========================================================== */

async function sendMessageToBackend(message) {
    try {
        const response = await fetch(
            "http://127.0.0.1:8000/chat",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json",
                },

                body: JSON.stringify({
                    message: message,
                    number_of_results: 3,
                }),
            }
        );

        if (!response.ok) {
            const error = await response.json();

            throw new Error(
                error.detail || "The server returned an error."
            );
        }

        return await response.json();

    } catch (error) {
        console.error("Chat error:", error);

        return {
            error: error.message,
        };
    }
}


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

function addAssistantMessage(response) {
    const message = document.createElement("div");

    message.className = "message assistant-message";

    if (response.error) {
        message.innerHTML = `
            <div class="assistant-label">
                IT Copilot
            </div>

            <div class="message-content">
                <p>
                    I couldn't connect to the IT Copilot server.
                </p>

                <p class="error-message">
                    ${escapeHtml(response.error)}
                </p>
            </div>
        `;

        messages.appendChild(message);

        scrollToBottom();

        return;
    }

    const sources = response.sources || [];

    const sourceHtml = sources.length > 0
        ? `
            <div class="sources">
                <div class="sources-title">
                    Sources
                </div>

                ${sources.map((source) => `
                    <div class="source">
                        ${escapeHtml(source.category)}
                        ·
                        ${escapeHtml(source.filename)}
                    </div>
                `).join("")}
            </div>
        `
        : "";

    message.innerHTML = `
        <div class="assistant-label">
            IT Copilot
        </div>

        <div class="message-content">
            ${formatResponse(response.answer)}

            ${sourceHtml}
        </div>
    `;

    messages.appendChild(message);

    scrollToBottom();
}


/* ==========================================================
   Markdown Rendering
   ========================================================== */

function formatResponse(text) {
    if (!text) {
        return "";
    }

    const codeBlocks = [];

    let escaped = escapeHtml(text)
        .replace(/\r\n/g, "\n")
        .replace(/\r/g, "\n");

    /*
     * Extract fenced code blocks before processing the rest
     * of the Markdown.
     */
    escaped = escaped.replace(
        /```[^\n]*\n([\s\S]*?)```/g,
        (match, code) => {
            const index = codeBlocks.length;

            codeBlocks.push(
                `<pre><code>${code.trim()}</code></pre>`
            );

            return `@@CODE_BLOCK_${index}@@`;
        }
    );

    const lines = escaped.split("\n");

    const output = [];

    let listType = null;

    function closeList() {
        if (listType === "ul") {
            output.push("</ul>");
        }

        if (listType === "ol") {
            output.push("</ol>");
        }

        listType = null;
    }

    for (let index = 0; index < lines.length; index++) {
        const line = lines[index];
        const nextLine = lines[index + 1] || "";

        if (!line.trim()) {
            closeList();
            continue;
        }


        /* --------------------------------------------------
           Tables
           -------------------------------------------------- */

        if (
            line.includes("|") &&
            isTableSeparator(nextLine)
        ) {
            closeList();

            const tableLines = [
                line,
                nextLine,
            ];

            index += 2;

            while (
                index < lines.length &&
                lines[index].includes("|") &&
                lines[index].trim()
            ) {
                tableLines.push(lines[index]);

                index++;
            }

            index--;

            output.push(
                renderTable(tableLines)
            );

            continue;
        }


        /* --------------------------------------------------
           Headings
           -------------------------------------------------- */

        const headingMatch = line.match(
            /^(#{1,6})\s+(.+)$/
        );

        if (headingMatch) {
            closeList();

            const level = headingMatch[1].length;

            output.push(
                `<h${level}>${formatInlineMarkdown(
                    headingMatch[2]
                )}</h${level}>`
            );

            continue;
        }


        /* --------------------------------------------------
           Horizontal Rule
           -------------------------------------------------- */

        if (
            /^(\*{3,}|-{3,}|_{3,})$/.test(
                line.trim()
            )
        ) {
            closeList();

            output.push("<hr>");

            continue;
        }


        /* --------------------------------------------------
           Unordered List
           -------------------------------------------------- */

        const unorderedMatch = line.match(
            /^\s*[-*+]\s+(.+)$/
        );

        if (unorderedMatch) {
            if (listType !== "ul") {
                closeList();

                output.push("<ul>");

                listType = "ul";
            }

            output.push(
                `<li>${formatInlineMarkdown(
                    unorderedMatch[1]
                )}</li>`
            );

            continue;
        }


        /* --------------------------------------------------
           Ordered List
           -------------------------------------------------- */

        const orderedMatch = line.match(
            /^\s*\d+\.\s+(.+)$/
        );

        if (orderedMatch) {
            if (listType !== "ol") {
                closeList();

                output.push("<ol>");

                listType = "ol";
            }

            output.push(
                `<li>${formatInlineMarkdown(
                    orderedMatch[1]
                )}</li>`
            );

            continue;
        }


        /* --------------------------------------------------
           Code Block
           -------------------------------------------------- */

        if (
            line.includes("@@CODE_BLOCK_")
        ) {
            closeList();

            output.push(line);

            continue;
        }


        /* --------------------------------------------------
           Regular Paragraph
           -------------------------------------------------- */

        closeList();

        output.push(
            `<p>${formatInlineMarkdown(line)}</p>`
        );
    }

    closeList();

    let result = output.join("");

    codeBlocks.forEach((codeBlock, index) => {
        result = result.replace(
            `@@CODE_BLOCK_${index}@@`,
            codeBlock
        );
    });

    return result;
}


/* ==========================================================
   Inline Markdown
   ========================================================== */

function formatInlineMarkdown(text) {
    let result = text;

    result = result.replace(
        /`([^`]+)`/g,
        "<code>$1</code>"
    );

    result = result.replace(
        /\*\*(.+?)\*\*/g,
        "<strong>$1</strong>"
    );

    result = result.replace(
        /(?<!\*)\*([^*]+)\*(?!\*)/g,
        "<em>$1</em>"
    );

    result = result.replace(
        /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    );

    return result;
}


/* ==========================================================
   Markdown Tables
   ========================================================== */

function isTableSeparator(line) {
    const cells = line
        .trim()
        .replace(/^\|/, "")
        .replace(/\|$/, "")
        .split("|");

    if (cells.length === 0) {
        return false;
    }

    return cells.every((cell) => {
        return /^\s*:?-{3,}:?\s*$/.test(cell);
    });
}


function renderTable(lines) {
    if (lines.length < 2) {
        return "";
    }

    const headerCells = parseTableRow(lines[0]);

    const bodyLines = lines.slice(2);

    let html = `
        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
    `;

    headerCells.forEach((cell) => {
        html += `
            <th>
                ${formatInlineMarkdown(cell)}
            </th>
        `;
    });

    html += `
                    </tr>
                </thead>

                <tbody>
    `;

    bodyLines.forEach((line) => {
        const cells = parseTableRow(line);

        html += "<tr>";

        cells.forEach((cell) => {
            html += `
                <td>
                    ${formatInlineMarkdown(cell)}
                </td>
            `;
        });

        html += "</tr>";
    });

    html += `
                </tbody>
            </table>
        </div>
    `;

    return html;
}


function parseTableRow(line) {
    return line
        .trim()
        .replace(/^\|/, "")
        .replace(/\|$/, "")
        .split("|")
        .map((cell) => cell.trim());
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