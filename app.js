const chatFeed = document.getElementById("chat-feed");
const askForm = document.getElementById("ask-form");
const input = document.getElementById("question-input");
const submitButton = document.getElementById("submit-button");
const logoutButton = document.getElementById("logout-button");
const authUsernameLabel = document.getElementById("auth-username-label");
const historyList = document.getElementById("history-list");
const historyCount = document.getElementById("history-count");
const initialChatMarkup = chatFeed.innerHTML;

let authState = {
    authenticated: false,
    username: "",
};
let historyState = [];
let activeHistoryId = "";

function escapeHtml(text) {
    return text
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
}

function escapeAttr(text) {
    return escapeHtml(text).replaceAll('"', "&quot;");
}

function normalizeMarkdownText(text) {
    return text
        .replaceAll("&nbsp;", " ")
        .replace(/<\/?[A-Za-z][^>]*>/g, "");
}

function normalizeSourceSnippet(text) {
    const lines = normalizeMarkdownText(text).replaceAll("\r\n", "\n").split("\n");
    while (lines.length) {
        const current = lines[0].trim();
        if (!current || current === "]" || current === "\\]") {
            lines.shift();
            continue;
        }
        break;
    }
    return lines.join("\n").trim();
}

function findMatchingBrace(text, startIndex) {
    if (text[startIndex] !== "{") {
        return -1;
    }

    let depth = 0;
    for (let index = startIndex; index < text.length; index += 1) {
        if (text[index] === "{") {
            depth += 1;
        } else if (text[index] === "}") {
            depth -= 1;
            if (depth === 0) {
                return index;
            }
        }
    }

    return -1;
}

function renderMathExpression(input) {
    const expression = input.trim();
    const commandMap = {
        alpha: "α",
        beta: "β",
        gamma: "γ",
        theta: "θ",
        mu: "μ",
        sigma: "σ",
        lambda: "λ",
        pi: "π",
        infty: "∞",
        cdot: "·",
        times: "×",
        pm: "±",
        neq: "≠",
        ge: "≥",
        le: "≤",
        in: "∈",
        notin: "∉",
        subset: "⊂",
        subseteq: "⊆",
        superset: "⊃",
        supseteq: "⊇",
        to: "→",
        rightarrow: "→",
        leftarrow: "←",
        Rightarrow: "⇒",
        Leftarrow: "⇐",
        approx: "≈",
        min: "min",
        max: "max",
        sum: "∑",
        prod: "∏",
        cup: "∪",
        cap: "∩",
        cos: "cos",
        sin: "sin",
        tan: "tan",
        log: "log",
    };

    function renderAtom(text, startIndex) {
        if (startIndex >= text.length) {
            return { html: "", nextIndex: startIndex };
        }

        const current = text[startIndex];
        if (current === "{") {
            const endIndex = findMatchingBrace(text, startIndex);
            if (endIndex === -1) {
                return { html: escapeHtml(current), nextIndex: startIndex + 1 };
            }
            return {
                html: renderSegment(text.slice(startIndex + 1, endIndex)),
                nextIndex: endIndex + 1,
            };
        }

        if (current === "\\") {
            let index = startIndex + 1;
            while (index < text.length && /[A-Za-z]/.test(text[index])) {
                index += 1;
            }

            if (index === startIndex + 1) {
                const symbol = text[index] || "";
                const mapped = {
                    "\\": "\\",
                    "{": "{",
                    "}": "}",
                    "|": "‖",
                    "_": "_",
                    "^": "^",
                }[symbol] ?? symbol;
                return {
                    html: escapeHtml(mapped),
                    nextIndex: Math.min(index + 1, text.length),
                };
            }

            const command = text.slice(startIndex + 1, index);
            if (command === "frac") {
                const numerator = renderAtom(text, index);
                const denominator = renderAtom(text, numerator.nextIndex);
                return {
                    html: `<span class="math-frac"><span class="math-num">${numerator.html}</span><span class="math-den">${denominator.html}</span></span>`,
                    nextIndex: denominator.nextIndex,
                };
            }

            if (["text", "mathrm"].includes(command)) {
                const group = renderAtom(text, index);
                return {
                    html: `<span class="math-text">${group.html}</span>`,
                    nextIndex: group.nextIndex,
                };
            }

            if (["mathbf", "mathbb"].includes(command)) {
                const group = renderAtom(text, index);
                return {
                    html: `<span class="math-bold">${group.html}</span>`,
                    nextIndex: group.nextIndex,
                };
            }

            if (command === "bar") {
                const group = renderAtom(text, index);
                return {
                    html: `<span class="math-overline">${group.html}</span>`,
                    nextIndex: group.nextIndex,
                };
            }

            if (["left", "right"].includes(command)) {
                const next = renderAtom(text, index);
                return {
                    html: next.html,
                    nextIndex: next.nextIndex,
                };
            }

            return {
                html: escapeHtml(commandMap[command] ?? command),
                nextIndex: index,
            };
        }

        return {
            html: escapeHtml(current),
            nextIndex: startIndex + 1,
        };
    }

    function renderSegment(text) {
        let html = "";
        let index = 0;
        while (index < text.length) {
            const current = text[index];
            if (current === "^" || current === "_") {
                const atom = renderAtom(text, index + 1);
                html += current === "^"
                    ? `<sup>${atom.html}</sup>`
                    : `<sub>${atom.html}</sub>`;
                index = atom.nextIndex;
                continue;
            }

            const atom = renderAtom(text, index);
            html += atom.html;
            index = atom.nextIndex;
        }

        return html
            .replace(/\|/g, "|")
            .replace(/‖/g, "<span class=\"math-norm\">‖</span>");
    }

    return renderSegment(expression);
}

function replaceMathPlaceholders(text, placeholders) {
    let current = text;

    current = current.replace(/\$\$([\s\S]+?)\$\$/g, (_, expr) => {
        const placeholder = `@@MATHBLOCK${placeholders.length}@@`;
        placeholders.push(`<span class="math-block">${renderMathExpression(expr)}</span>`);
        return placeholder;
    });

    current = current.replace(/\\\[([\s\S]+?)\\\]/g, (_, expr) => {
        const placeholder = `@@MATHBLOCK${placeholders.length}@@`;
        placeholders.push(`<span class="math-block">${renderMathExpression(expr)}</span>`);
        return placeholder;
    });

    current = current.replace(/\\\(([\s\S]+?)\\\)/g, (_, expr) => {
        const placeholder = `@@MATHINLINE${placeholders.length}@@`;
        placeholders.push(`<span class="math-inline">${renderMathExpression(expr)}</span>`);
        return placeholder;
    });

    current = current.replace(/\(([^()\n]*\\[A-Za-z]+[^()\n]*)\)/g, (_, expr) => {
        const placeholder = `@@MATHINLINE${placeholders.length}@@`;
        placeholders.push(`<span class="math-inline">${renderMathExpression(`(${expr})`)}</span>`);
        return placeholder;
    });

    current = current.replace(/(^|[^$])\$([^$\n]+)\$/g, (match, prefix, expr) => {
        const placeholder = `@@MATHINLINE${placeholders.length}@@`;
        placeholders.push(`<span class="math-inline">${renderMathExpression(expr)}</span>`);
        return `${prefix}${placeholder}`;
    });

    return current;
}

function renderInlineMarkdown(text) {
    const codeSpans = [];
    const mathSpans = [];
    let rendered = replaceMathPlaceholders(normalizeMarkdownText(text), mathSpans);
    rendered = escapeHtml(rendered);

    rendered = rendered.replace(/`([^`]+)`/g, (_, code) => {
        const placeholder = `@@CODESPAN${codeSpans.length}@@`;
        codeSpans.push(`<code>${code}</code>`);
        return placeholder;
    });

    rendered = rendered.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_, label, url) => {
        return `<a href="${escapeAttr(url)}" target="_blank" rel="noreferrer">${label}</a>`;
    });
    rendered = rendered.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    rendered = rendered.replace(/__([^_]+)__/g, "<strong>$1</strong>");
    rendered = rendered.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
    rendered = rendered.replace(/_([^_\n]+)_/g, "<em>$1</em>");

    for (let index = 0; index < codeSpans.length; index += 1) {
        rendered = rendered.replace(`@@CODESPAN${index}@@`, codeSpans[index]);
    }

    for (let index = mathSpans.length - 1; index >= 0; index -= 1) {
        rendered = rendered.replace(`@@MATHBLOCK${index}@@`, mathSpans[index]);
        rendered = rendered.replace(`@@MATHINLINE${index}@@`, mathSpans[index]);
    }

    return rendered;
}

function renderMarkdown(markdown) {
    const lines = markdown.replaceAll("\r\n", "\n").split("\n");
    const blocks = [];
    let paragraphLines = [];

    function flushParagraph() {
        if (!paragraphLines.length) {
            return;
        }

        blocks.push(`<p>${paragraphLines.map((line) => renderInlineMarkdown(line)).join("<br>")}</p>`);
        paragraphLines = [];
    }

    for (let index = 0; index < lines.length; index += 1) {
        const line = lines[index];
        const trimmed = line.trim();

        if (!trimmed) {
            flushParagraph();
            continue;
        }

        if (/^```/.test(trimmed)) {
            flushParagraph();
            const codeLines = [];
            index += 1;
            while (index < lines.length && !/^```/.test(lines[index].trim())) {
                codeLines.push(lines[index]);
                index += 1;
            }
            blocks.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
            continue;
        }

        if (/^\$\$$/.test(trimmed)) {
            flushParagraph();
            const mathLines = [];
            index += 1;
            while (index < lines.length && !/^\$\$$/.test(lines[index].trim())) {
                mathLines.push(lines[index]);
                index += 1;
            }
            blocks.push(`<div class="math-block">${renderMathExpression(mathLines.join(" "))}</div>`);
            continue;
        }

        if (/^\[$/.test(trimmed)) {
            flushParagraph();
            const mathLines = [];
            index += 1;
            while (index < lines.length && !/^\]$/.test(lines[index].trim())) {
                mathLines.push(lines[index]);
                index += 1;
            }
            blocks.push(`<div class="math-block">${renderMathExpression(mathLines.join(" "))}</div>`);
            continue;
        }

        if (/^\\\[$/.test(trimmed)) {
            flushParagraph();
            const mathLines = [];
            index += 1;
            while (index < lines.length && !/^\\\]$/.test(lines[index].trim())) {
                mathLines.push(lines[index]);
                index += 1;
            }
            blocks.push(`<div class="math-block">${renderMathExpression(mathLines.join(" "))}</div>`);
            continue;
        }

        const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
        if (headingMatch) {
            flushParagraph();
            const level = headingMatch[1].length;
            blocks.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
            continue;
        }

        if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
            flushParagraph();
            blocks.push("<hr>");
            continue;
        }

        if (/^>\s+/.test(trimmed)) {
            flushParagraph();
            const quoteLines = [trimmed.replace(/^>\s+/, "")];
            while (index + 1 < lines.length && /^>\s+/.test(lines[index + 1].trim())) {
                index += 1;
                quoteLines.push(lines[index].trim().replace(/^>\s+/, ""));
            }
            blocks.push(`<blockquote>${quoteLines.map((item) => renderInlineMarkdown(item)).join("<br>")}</blockquote>`);
            continue;
        }

        const unorderedMatch = trimmed.match(/^[-*+]\s+(.+)$/);
        if (unorderedMatch) {
            flushParagraph();
            const items = [unorderedMatch[1]];
            while (index + 1 < lines.length) {
                const next = lines[index + 1].trim().match(/^[-*+]\s+(.+)$/);
                if (!next) {
                    break;
                }
                index += 1;
                items.push(next[1]);
            }
            blocks.push(`<ul>${items.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("")}</ul>`);
            continue;
        }

        const orderedMatch = trimmed.match(/^\d+\.\s+(.+)$/);
        if (orderedMatch) {
            flushParagraph();
            const items = [orderedMatch[1]];
            while (index + 1 < lines.length) {
                const next = lines[index + 1].trim().match(/^\d+\.\s+(.+)$/);
                if (!next) {
                    break;
                }
                index += 1;
                items.push(next[1]);
            }
            blocks.push(`<ol>${items.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("")}</ol>`);
            continue;
        }

        paragraphLines.push(trimmed);
    }

    flushParagraph();
    return blocks.join("");
}

function buildSourceHref(source) {
    if (!source.path) {
        return "";
    }

    const base = `/api/source?path=${encodeURIComponent(source.path)}`;
    if (source.page_number && source.path.toLowerCase().endsWith(".pdf")) {
        return `${base}#page=${source.page_number}`;
    }
    return base;
}

function renderSourcesInline(sources) {
    if (!sources.length) {
        return "";
    }

    const items = sources.map((source) => {
        const sourceHref = buildSourceHref(source);
        const pageLabel = source.page_number ? `p.${source.page_number}` : "";
        const sectionLabel = source.section_heading || source.page_heading || "";
        const sourceSnippet = normalizeSourceSnippet(source.snippet || "");
        return `
            <article class="inline-source-item">
                <div class="inline-source-meta">
                    <span class="source-score">score ${source.score}</span>
                    ${pageLabel ? `<span class="source-page">${escapeHtml(pageLabel)}</span>` : ""}
                </div>
                <h4 class="source-title">
                    ${sourceHref
                        ? `<a class="source-link" href="${escapeAttr(sourceHref)}" target="_blank" rel="noreferrer">${escapeHtml(source.title)}</a>`
                        : escapeHtml(source.title)}
                </h4>
                ${sectionLabel ? `<div class="source-heading">${escapeHtml(sectionLabel)}</div>` : ""}
                <div class="source-path">
                    ${sourceHref
                        ? `<a class="source-link source-path-link" href="${escapeAttr(sourceHref)}" target="_blank" rel="noreferrer">${escapeHtml(source.path)}</a>`
                        : escapeHtml(source.path)}
                </div>
                <div class="source-snippet markdown-body">${renderMarkdown(sourceSnippet)}</div>
            </article>
        `;
    }).join("");

    return `
        <details class="turn-sources">
            <summary>来源 ${sources.length}</summary>
            <div class="turn-source-list">${items}</div>
        </details>
    `;
}

function createTurnElement(question, answer, mode = "", sources = [], isPending = false) {
    const article = document.createElement("article");
    article.className = `turn-card${isPending ? " is-pending" : ""}`;
    article.innerHTML = `
        <div class="turn-question">${escapeHtml(question)}</div>
        <div class="turn-answer-shell">
            <div class="turn-answer-head">
                <span class="turn-role">知识助手</span>
                <span class="mode-badge">${escapeHtml(mode || "answer")}</span>
            </div>
            <div class="turn-answer markdown-body">${renderMarkdown(answer)}</div>
            ${renderSourcesInline(sources)}
        </div>
    `;
    return article;
}

function appendTurn(question, answer, mode = "", sources = [], isPending = false) {
    if (chatFeed.querySelector(".welcome-panel")) {
        chatFeed.innerHTML = "";
    }
    const article = createTurnElement(question, answer, mode, sources, isPending);
    chatFeed.appendChild(article);
    chatFeed.scrollTop = chatFeed.scrollHeight;
    return article;
}

function updateTurn(article, question, answer, mode = "", sources = [], isPending = false) {
    const next = createTurnElement(question, answer, mode, sources, isPending);
    if (article.dataset.turnId) {
        next.dataset.turnId = article.dataset.turnId;
    }
    article.replaceWith(next);
    chatFeed.scrollTop = chatFeed.scrollHeight;
    return next;
}

function redirectToLogin() {
    window.location.replace("/login");
}

function formatHistoryTime(value) {
    if (!value) {
        return "";
    }
    const timestamp = new Date(value);
    if (Number.isNaN(timestamp.getTime())) {
        return value;
    }
    return timestamp.toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function truncateText(text, limit = 88) {
    const normalized = (text || "").replace(/\s+/g, " ").trim();
    if (normalized.length <= limit) {
        return normalized;
    }
    return `${normalized.slice(0, limit - 1)}…`;
}

function resetConversationView() {
    chatFeed.innerHTML = initialChatMarkup;
    chatFeed.scrollTop = 0;
}

function showHistoryRecord(record) {
    resetConversationView();
    const turn = appendTurn(
        record.question || "",
        record.answer || "",
        record.mode || "history",
        record.sources || [],
        false,
    );
    if (record.id) {
        turn.dataset.turnId = record.id;
    }
}

async function deleteHistoryRecord(recordId) {
    if (!recordId) {
        return;
    }
    if (!window.confirm("确认删除这条历史记录？")) {
        return;
    }

    try {
        let response = await fetch(`/api/history/${encodeURIComponent(recordId)}`, {
            method: "DELETE",
        });
        if (response.status === 404) {
            response = await fetch("/api/history/delete", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ record_id: recordId }),
            });
        }
        if (response.status === 401) {
            redirectToLogin();
            return;
        }
        if (!response.ok) {
            return;
        }

        if (activeHistoryId === recordId) {
            activeHistoryId = "";
            resetConversationView();
        }
        await loadHistory();
    } catch (error) {
        // Keep the UI stable when deletion fails.
    }
}

function renderHistory(records) {
    historyState = records || [];
    historyCount.textContent = String(historyState.length);
    historyList.innerHTML = "";

    if (!historyState.length) {
        historyList.innerHTML = `<p class="empty-state">当前用户还没有历史记录。提问一次，这里就会出现。</p>`;
        return;
    }

    for (const record of historyState) {
        const item = document.createElement("article");
        item.className = "history-item";
        if (record.id === activeHistoryId) {
            item.classList.add("is-active");
        }
        item.innerHTML = `
            <div class="history-item-head">
                <div class="history-item-meta">
                    <span class="history-item-time">${escapeHtml(formatHistoryTime(record.created_at))}</span>
                    <span class="history-item-mode">${escapeHtml(record.mode || "history")}</span>
                </div>
                <button class="history-delete-button" type="button" aria-label="删除历史记录" title="删除这条历史记录">×</button>
            </div>
            <button class="history-open-button" type="button">
                <p class="history-item-question">${escapeHtml(record.question || "")}</p>
                <p class="history-item-answer">${escapeHtml(record.answer || "")}</p>
            </button>
        `;
        const openButton = item.querySelector(".history-open-button");
        const deleteButton = item.querySelector(".history-delete-button");
        openButton.addEventListener("click", () => {
            activeHistoryId = record.id || "";
            renderHistory(historyState);
            showHistoryRecord(record);
        });
        deleteButton.addEventListener("click", async (event) => {
            event.stopPropagation();
            await deleteHistoryRecord(record.id || "");
        });
        historyList.appendChild(item);
    }
}

async function loadHistory(selectedId = "") {
    try {
        const response = await fetch("/api/history");
        const payload = await response.json();
        if (!response.ok || !payload.authenticated) {
            redirectToLogin();
            return;
        }

        authState = {
            authenticated: true,
            username: payload.username || authState.username,
        };
        authUsernameLabel.textContent = authState.username;
        activeHistoryId = selectedId || activeHistoryId;
        renderHistory(payload.history || []);
    } catch (error) {
        historyList.innerHTML = `<p class="empty-state">历史记录读取失败，请稍后重试。</p>`;
        historyCount.textContent = "0";
    }
}

async function refreshAuthState() {
    try {
        const response = await fetch("/api/auth/me");
        const payload = await response.json();
        if (!response.ok || !payload.authenticated) {
            redirectToLogin();
            return;
        }

        authState = {
            authenticated: Boolean(payload.authenticated),
            username: payload.username || "",
        };
        authUsernameLabel.textContent = authState.username;
        await loadHistory();
    } catch (error) {
        redirectToLogin();
    }
}

async function ask(question) {
    const trimmed = question.trim();
    if (!trimmed) {
        return;
    }

    const loadingTurn = appendTurn(trimmed, "正在检索资料并整理回答...", "loading", [], true);

    submitButton.disabled = true;
    submitButton.textContent = "检索中";

    try {
        const response = await fetch("/api/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question: trimmed }),
        });
        if (response.status === 401) {
            redirectToLogin();
            return;
        }
        const payload = await response.json();
        const savedTurn = updateTurn(
            loadingTurn,
            trimmed,
            payload.answer,
            payload.mode,
            payload.sources || [],
            false,
        );
        if (payload.history_id) {
            savedTurn.dataset.turnId = payload.history_id;
        }
        if (payload.history_saved) {
            await loadHistory(payload.history_id || "");
        }
    } catch (error) {
        updateTurn(
            loadingTurn,
            trimmed,
            "请求失败，请检查后端是否正常运行。",
            "error",
            [],
            false,
        );
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = "发送";
        chatFeed.scrollTop = chatFeed.scrollHeight;
    }
}

logoutButton.addEventListener("click", async () => {
    logoutButton.disabled = true;
    try {
        await fetch("/api/auth/logout", { method: "POST" });
        redirectToLogin();
    } catch (error) {
        logoutButton.disabled = false;
    } finally {
        logoutButton.disabled = false;
    }
});

askForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = input.value;
    input.value = "";
    autoResizeComposer();
    await ask(question);
});

document.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
        return;
    }
    const button = target.closest(".suggestion-chip");
    if (!button) {
        return;
    }
    const question = button.dataset.question || "";
    input.value = "";
    autoResizeComposer();
    await ask(question);
});

function autoResizeComposer() {
    input.style.height = "0px";
    input.style.height = `${Math.min(input.scrollHeight, 220)}px`;
}

input.addEventListener("input", autoResizeComposer);
input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        askForm.requestSubmit();
    }
});

autoResizeComposer();

refreshAuthState();
