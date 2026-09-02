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
   Conversation
   ========================================================== */

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

    messages.innerHTML = "";

    addWelcomeMessage();

    messageInput.value = "";
    messageInput.style.height = "auto";

    closeSidebar();

    messageInput.focus();
}


sidebarNewChatButton.addEventListener(
    "click",
    startNewChat
);

newChatButton.addEventListener(
    "click",
    startNewChat
);


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
    document.querySelectorAll(".suggestion").forEach(
        (button) => {
            button.addEventListener(
                "click",
                () => {
                    messageInput.value =
                        button.textContent.trim();

                    resizeInput();

                    messageInput.focus();
                }
            );
        }
    );
}


/* ==========================================================
   Message Input
   ========================================================== */

function resizeInput() {
    messageInput.style.height = "auto";

    messageInput.style.height =
        `${Math.min(
            messageInput.scrollHeight,
            140
        )}px`;
}


messageInput.addEventListener(
    "input",
    resizeInput
);


messageInput.addEventListener(
    "keydown",
    (event) => {
        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {
            event.preventDefault();

            chatForm.requestSubmit();
        }
    }
);


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
                    conversation_id: conversationId,
                    number_of_results: 3,
                }),
            }
        );

        if (!response.ok) {
            const error = await response.json();

            throw new Error(
                error.detail ||
                "The server returned an error."
            );
        }

        return await response.json();

    } catch (error) {
        console.error(
            "Chat error:",
            error
        );

        return {
            error: error.message,
        };
    }
}


/* ==========================================================
   Add User Message
   ========================================================== */

function addUserMessage(text) {
    const message =
        document.createElement("div");

    message.className =
        "message user-message";

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
    const message =
        document.createElement("div");

    message.className =
        "message assistant-message";

    if (response.error) {
        message.innerHTML = `
            <div class="assistant-label">
                IT Copilot
            </div>

            <div class="message-content">
                <p>
                    I couldn't connect to the
                    IT Copilot server.
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

    /*
     * Store the conversation ID returned by
     * the backend.
     *
     * Follow-up messages will use this ID.
     */
    if (
        response.conversation_id !== undefined
    ) {
        conversationId =
            response.conversation_id;
    }

    const sources =
        response.sources || [];

    const sourceHtml =
        sources.length > 0
            ? `
                <div class="sources">
                    <div class="sources-title">
                        Sources
                    </div>

                    ${sources.map(
                        (source) => `
                            <div class="source">
                                ${escapeHtml(
                                    source.category
                                )}
                                ·
                                ${escapeHtml(
                                    source.filename
                                )}
                            </div>
                        `
                    ).join("")}
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

    let escaped =
        escapeHtml(text);

    escaped =
        escaped.replaceAll(
            "\r\n",
            "\n"
        );

    escaped =
        escaped.replaceAll(
            "\r",
            "\n"
        );


    /*
     * Extract fenced code blocks.
     */

    let processedText = "";

    let searchPosition = 0;

    while (true) {
        const start =
            escaped.indexOf(
                "```",
                searchPosition
            );

        if (start === -1) {
            processedText +=
                escaped.substring(
                    searchPosition
                );

            break;
        }

        processedText +=
            escaped.substring(
                searchPosition,
                start
            );

        const openingLineEnd =
            escaped.indexOf(
                "\n",
                start + 3
            );

        if (openingLineEnd === -1) {
            processedText +=
                escaped.substring(start);

            break;
        }

        const codeStart =
            openingLineEnd + 1;

        const closing =
            escaped.indexOf(
                "```",
                codeStart
            );

        if (closing === -1) {
            processedText +=
                escaped.substring(start);

            break;
        }

        const code =
            escaped.substring(
                codeStart,
                closing
            );

        const codeIndex =
            codeBlocks.length;

        codeBlocks.push(
            `<pre><code>${code.trim()}</code></pre>`
        );

        processedText +=
            `@@CODE_BLOCK_${codeIndex}@@`;

        searchPosition =
            closing + 3;
    }


    const lines =
        processedText.split("\n");

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


    for (
        let index = 0;
        index < lines.length;
        index++
    ) {
        const line =
            lines[index];

        const nextLine =
            lines[index + 1] || "";


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
                tableLines.push(
                    lines[index]
                );

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

        const heading =
            getHeading(line);

        if (heading !== null) {
            closeList();

            output.push(
                `<h${heading.level}>` +
                `${formatInlineMarkdown(
                    heading.text
                )}` +
                `</h${heading.level}>`
            );

            continue;
        }


        /* --------------------------------------------------
           Horizontal Rule
           -------------------------------------------------- */

        if (
            isHorizontalRule(
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

        const unordered =
            getUnorderedListItem(line);

        if (unordered !== null) {
            if (listType !== "ul") {
                closeList();

                output.push("<ul>");

                listType = "ul";
            }

            output.push(
                `<li>${formatInlineMarkdown(
                    unordered
                )}</li>`
            );

            continue;
        }


        /* --------------------------------------------------
           Ordered List
           -------------------------------------------------- */

        const ordered =
            getOrderedListItem(line);

        if (ordered !== null) {
            if (listType !== "ol") {
                closeList();

                output.push("<ol>");

                listType = "ol";
            }

            output.push(
                `<li>${formatInlineMarkdown(
                    ordered
                )}</li>`
            );

            continue;
        }


        /* --------------------------------------------------
           Code Block Placeholder
           -------------------------------------------------- */

        if (
            line.includes(
                "@@CODE_BLOCK_"
            )
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
            `<p>${formatInlineMarkdown(
                line
            )}</p>`
        );
    }


    closeList();


    let result =
        output.join("");


    codeBlocks.forEach(
        (codeBlock, index) => {
            result =
                result.replace(
                    `@@CODE_BLOCK_${index}@@`,
                    codeBlock
                );
        }
    );


    return result;
}


/* ==========================================================
   Inline Markdown
   ========================================================== */

function formatInlineMarkdown(text) {
    let result = text;


    /*
     * Inline code
     */

    result =
        replaceBetweenMarkers(
            result,
            "`",
            "<code>",
            "</code>"
        );


    /*
     * Bold
     */

    result =
        replaceBetweenMarkers(
            result,
            "**",
            "<strong>",
            "</strong>"
        );


    /*
     * Italic
     */

    result =
        replaceBetweenMarkers(
            result,
            "*",
            "<em>",
            "</em>"
        );


    return result;
}


/* ==========================================================
   Markdown Helpers
   ========================================================== */

function replaceBetweenMarkers(
    text,
    marker,
    openingTag,
    closingTag
) {
    let result = text;

    let searchPosition = 0;

    while (true) {
        const start =
            result.indexOf(
                marker,
                searchPosition
            );

        if (start === -1) {
            break;
        }

        const contentStart =
            start + marker.length;

        const end =
            result.indexOf(
                marker,
                contentStart
            );

        if (end === -1) {
            break;
        }

        const content =
            result.substring(
                contentStart,
                end
            );

        const replacement =
            openingTag +
            content +
            closingTag;

        result =
            result.substring(
                0,
                start
            ) +
            replacement +
            result.substring(
                end + marker.length
            );

        searchPosition =
            start + replacement.length;
    }

    return result;
}


function getHeading(line) {
    let level = 0;

    while (
        level < line.length &&
        line.charAt(level) === "#"
    ) {
        level++;
    }

    if (
        level === 0 ||
        level > 6
    ) {
        return null;
    }

    if (
        line.charAt(level) !== " "
    ) {
        return null;
    }

    return {
        level: level,
        text: line.substring(
            level + 1
        ),
    };
}


function isHorizontalRule(line) {
    if (line.length < 3) {
        return false;
    }

    const first =
        line.charAt(0);

    if (
        first !== "-" &&
        first !== "*" &&
        first !== "_"
    ) {
        return false;
    }

    for (
        let index = 0;
        index < line.length;
        index++
    ) {
        if (
            line.charAt(index) !== first
        ) {
            return false;
        }
    }

    return true;
}


function getUnorderedListItem(line) {
    const trimmed =
        line.trim();

    if (
        trimmed.startsWith("- ")
    ) {
        return trimmed.substring(2);
    }

    if (
        trimmed.startsWith("* ")
    ) {
        return trimmed.substring(2);
    }

    if (
        trimmed.startsWith("+ ")
    ) {
        return trimmed.substring(2);
    }

    return null;
}


function getOrderedListItem(line) {
    const trimmed =
        line.trim();

    const dot =
        trimmed.indexOf(".");

    if (
        dot <= 0 ||
        dot + 1 >= trimmed.length
    ) {
        return null;
    }

    const number =
        trimmed.substring(
            0,
            dot
        );

    for (
        let index = 0;
        index < number.length;
        index++
    ) {
        const character =
            number.charAt(index);

        if (
            character < "0" ||
            character > "9"
        ) {
            return null;
        }
    }

    if (
        trimmed.charAt(dot + 1) !== " "
    ) {
        return null;
    }

    return trimmed.substring(
        dot + 2
    );
}


/* ==========================================================
   Markdown Tables
   ========================================================== */

function isTableSeparator(line) {
    const cells =
        parseTableRow(line);

    if (cells.length === 0) {
        return false;
    }

    return cells.every(
        (cell) => {
            let value =
                cell.trim();

            if (
                value.startsWith(":")
            ) {
                value =
                    value.substring(1);
            }

            if (
                value.endsWith(":")
            ) {
                value =
                    value.substring(
                        0,
                        value.length - 1
                    );
            }

            if (value.length < 3) {
                return false;
            }

            for (
                let index = 0;
                index < value.length;
                index++
            ) {
                if (
                    value.charAt(index) !== "-"
                ) {
                    return false;
                }
            }

            return true;
        }
    );
}


function renderTable(lines) {
    if (lines.length < 2) {
        return "";
    }

    const headerCells =
        parseTableRow(lines[0]);

    const bodyLines =
        lines.slice(2);

    let html = `
        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
    `;


    headerCells.forEach(
        (cell) => {
            html += `
                <th>
                    ${formatInlineMarkdown(
                        cell
                    )}
                </th>
            `;
        }
    );


    html += `
                    </tr>
                </thead>

                <tbody>
    `;


    bodyLines.forEach(
        (line) => {
            const cells =
                parseTableRow(line);

            html += "<tr>";

            cells.forEach(
                (cell) => {
                    html += `
                        <td>
                            ${formatInlineMarkdown(
                                cell
                            )}
                        </td>
                    `;
                }
            );

            html += "</tr>";
        }
    );


    html += `
                </tbody>
            </table>
        </div>
    `;


    return html;
}


function parseTableRow(line) {
    let value =
        line.trim();

    if (
        value.startsWith("|")
    ) {
        value =
            value.substring(1);
    }

    if (
        value.endsWith("|")
    ) {
        value =
            value.substring(
                0,
                value.length - 1
            );
    }

    return value
        .split("|")
        .map(
            (cell) => cell.trim()
        );
}


/* ==========================================================
   Form Submission
   ========================================================== */

chatForm.addEventListener(
    "submit",
    async (event) => {
        event.preventDefault();

        const message =
            messageInput.value.trim();

        if (!message) {
            return;
        }

        messages
            .querySelector(".welcome")
            ?.remove();

        addUserMessage(message);

        messageInput.value = "";

        messageInput.style.height =
            "auto";

        const response =
            await sendMessageToBackend(
                message
            );

        addAssistantMessage(
            response
        );
    }
);


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
    const element =
        document.createElement("div");

    element.textContent = text;

    return element.innerHTML;
}