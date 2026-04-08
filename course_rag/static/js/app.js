const chatFeed = document.getElementById("chat-feed");
const askForm = document.getElementById("ask-form");
const input = document.getElementById("question-input");
const submitButton = document.getElementById("submit-button");
const logoutButton = document.getElementById("logout-button");
const filesButton = document.getElementById("files-button");
const uploadButton = document.getElementById("upload-button");
const uploadInput = document.getElementById("upload-input");
const statsDocuments = document.getElementById("stats-documents");
const statsChunks = document.getElementById("stats-chunks");
const appToast = document.getElementById("app-toast");
const filesOverlay = document.getElementById("files-overlay");
const filesCloseButton = document.getElementById("files-close");
const filesList = document.getElementById("files-list");
const filesCount = document.getElementById("files-count");
const startupOverlay = document.getElementById("startup-overlay");
const startupMessage = document.getElementById("startup-message");
const statusBackend = document.getElementById("status-backend");
const authUsernameLabel = document.getElementById("auth-username-label");
const historyList = document.getElementById("history-list");
const historyCount = document.getElementById("history-count");
let confirmOverlay = document.getElementById("confirm-overlay");
let confirmBadge = document.getElementById("confirm-badge");
let confirmTitle = document.getElementById("confirm-title");
let confirmMessage = document.getElementById("confirm-message");
let confirmAcceptButton = document.getElementById("confirm-accept");
let confirmCancelButton = document.getElementById("confirm-cancel");
const initialChatMarkup = chatFeed.innerHTML;

let authState = {
    authenticated: false,
    username: "",
};
let historyState = [];
let activeHistoryId = "";
let confirmResolver = null;
let confirmReturnFocus = null;
let toastTimer = null;
let filesPanelReturnFocus = null;
let startupBlocked = askForm?.dataset.indexing === "true";
let startupPollTimer = null;

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

function showToast(message, tone = "info") {
    if (!appToast) {
        return;
    }
    appToast.textContent = message;
    appToast.className = `app-toast is-${tone}`;
    appToast.hidden = false;

    if (toastTimer) {
        window.clearTimeout(toastTimer);
    }
    toastTimer = window.setTimeout(() => {
        appToast.hidden = true;
    }, 3200);
}

function clearStartupPoll() {
    if (startupPollTimer) {
        window.clearTimeout(startupPollTimer);
        startupPollTimer = null;
    }
}

function scheduleStartupPoll() {
    clearStartupPoll();
    startupPollTimer = window.setTimeout(checkStartupStatus, 3000);
}

function setStartupBlocked(indexing, message = "", backend = "") {
    startupBlocked = indexing;
    document.body.classList.toggle("modal-open", indexing);

    if (startupOverlay) {
        startupOverlay.hidden = !indexing;
    }
    if (startupMessage) {
        startupMessage.textContent = message || "正在向量化课程资料并准备检索索引，预计需要 1 分钟左右。";
    }
    if (statusBackend && backend) {
        statusBackend.textContent = `检索 ${backend}`;
    }

    if (input) {
        input.disabled = indexing;
        input.placeholder = indexing ? "知识库索引构建中，请稍候" : "有问题，尽管问";
    }
    if (submitButton) {
        submitButton.disabled = indexing;
        submitButton.textContent = indexing ? "构建中" : "发送";
    }

    if (indexing) {
        scheduleStartupPoll();
    } else {
        clearStartupPoll();
    }
}

async function checkStartupStatus() {
    try {
        const response = await fetch("/api/health");
        const payload = await response.json();
        updateStats(payload);
        const indexing = Boolean(payload.indexing) || payload.status === "indexing";
        setStartupBlocked(indexing, payload.message || "", payload.backend || "");
    } catch (error) {
        setStartupBlocked(true, "服务正在启动并构建知识库，请稍候。", "initializing");
    }
}

function formatFileSize(bytes) {
    const size = Number(bytes);
    if (!Number.isFinite(size) || size <= 0) {
        return "0 B";
    }

    const units = ["B", "KB", "MB", "GB"];
    let value = size;
    let unitIndex = 0;
    while (value >= 1024 && unitIndex < units.length - 1) {
        value /= 1024;
        unitIndex += 1;
    }
    return `${value >= 10 || unitIndex === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[unitIndex]}`;
}

function formatFileTime(timestamp) {
    const value = new Date(Number(timestamp) * 1000);
    if (Number.isNaN(value.getTime())) {
        return "";
    }
    return value.toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function updateStats(stats) {
    if (!stats) {
        return;
    }
    if (statsDocuments && Number.isFinite(Number(stats.documents))) {
        statsDocuments.textContent = String(stats.documents);
    }
    if (statsChunks && Number.isFinite(Number(stats.chunks))) {
        statsChunks.textContent = String(stats.chunks);
    }
}

function closeFilesPanel() {
    if (!filesOverlay) {
        return;
    }
    filesOverlay.hidden = true;
    document.body.classList.remove("modal-open");
    if (filesPanelReturnFocus) {
        filesPanelReturnFocus.focus();
    }
    filesPanelReturnFocus = null;
}

function renderFilesList(files) {
    if (!filesList || !filesCount) {
        return;
    }

    filesCount.textContent = `${files.length} 个文件`;
    if (!files.length) {
        filesList.innerHTML = `<p class="empty-state">当前还没有课程资料文件。先上传一个文件，这里就会出现。</p>`;
        return;
    }

    filesList.innerHTML = files.map((file) => {
        const href = buildSourceHref({ path: file.path });
        const ext = (file.doc_type || "").replace(".", "").toUpperCase() || "FILE";
        return `
            <article class="file-item">
                <div class="file-item-icon">${escapeHtml(ext)}</div>
                <div class="file-item-body">
                    <div class="file-item-meta">
                        <span>${escapeHtml(ext)}</span>
                        <span>${escapeHtml(formatFileSize(file.size_bytes))}</span>
                        <span>${escapeHtml(formatFileTime(file.updated_at))}</span>
                    </div>
                    <div class="file-item-name">${escapeHtml(file.name || file.title || "")}</div>
                    <div class="file-item-path">${escapeHtml(file.path || "")}</div>
                </div>
                <div class="file-item-actions">
                    <a class="ghost-button file-open-button" href="${escapeAttr(href)}" target="_blank" rel="noreferrer">打开</a>
                    <button
                        class="file-delete-button"
                        type="button"
                        data-file-path="${escapeAttr(file.path || "")}"
                        data-file-name="${escapeAttr(file.name || file.title || "")}"
                    >删除</button>
                </div>
            </article>
        `;
    }).join("");
}

async function loadFilesList() {
    if (!filesList || !filesCount) {
        return;
    }

    filesList.innerHTML = `<p class="empty-state">正在读取文件列表...</p>`;
    try {
        const response = await fetch("/api/files");
        const payload = await response.json();
        if (response.status === 401) {
            redirectToLogin();
            return;
        }
        if (!response.ok) {
            filesList.innerHTML = `<p class="empty-state">文件列表读取失败，请稍后重试。</p>`;
            filesCount.textContent = "0 个文件";
            return;
        }
        renderFilesList(payload.files || []);
    } catch (error) {
        filesList.innerHTML = `<p class="empty-state">文件列表读取失败，请稍后重试。</p>`;
        filesCount.textContent = "0 个文件";
    }
}

async function openFilesPanel() {
    if (!filesOverlay) {
        return;
    }
    filesPanelReturnFocus = document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    filesOverlay.hidden = false;
    document.body.classList.add("modal-open");
    await loadFilesList();
    filesCloseButton?.focus();
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

function closeConfirmDialog(confirmed) {
    if (!confirmResolver || !confirmOverlay) {
        return;
    }
    const resolve = confirmResolver;
    confirmResolver = null;
    confirmOverlay.hidden = true;
    document.body.classList.remove("modal-open");
    if (confirmReturnFocus) {
        confirmReturnFocus.focus();
    }
    confirmReturnFocus = null;
    resolve(confirmed);
}

function wireConfirmDialog() {
    if (!confirmOverlay || confirmOverlay.dataset.bound === "true") {
        return;
    }

    confirmAcceptButton?.addEventListener("click", () => {
        closeConfirmDialog(true);
    });

    confirmCancelButton?.addEventListener("click", () => {
        closeConfirmDialog(false);
    });

    confirmOverlay.addEventListener("click", (event) => {
        if (event.target === confirmOverlay) {
            closeConfirmDialog(false);
        }
    });

    confirmOverlay.dataset.bound = "true";
}

function ensureConfirmDialog() {
    if (!confirmOverlay) {
        const wrapper = document.createElement("div");
        wrapper.innerHTML = `
            <div id="confirm-overlay" class="confirm-overlay" hidden>
                <div class="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-message">
                    <div id="confirm-badge" class="confirm-badge">删除确认</div>
                    <h3 id="confirm-title" class="confirm-title">删除这条历史记录？</h3>
                    <p id="confirm-message" class="confirm-message">删除后将无法恢复，这条问答记录会从当前账号的本地历史中移除。</p>
                    <div class="confirm-actions">
                        <button id="confirm-cancel" class="ghost-button" type="button">取消</button>
                        <button id="confirm-accept" class="danger-button" type="button">确认删除</button>
                    </div>
                </div>
            </div>
        `.trim();
        document.body.appendChild(wrapper.firstElementChild);
        confirmOverlay = document.getElementById("confirm-overlay");
        confirmBadge = document.getElementById("confirm-badge");
        confirmTitle = document.getElementById("confirm-title");
        confirmMessage = document.getElementById("confirm-message");
        confirmAcceptButton = document.getElementById("confirm-accept");
        confirmCancelButton = document.getElementById("confirm-cancel");
    }

    wireConfirmDialog();
    return Boolean(confirmOverlay && confirmAcceptButton && confirmCancelButton);
}

function configureConfirmDialog(options = {}) {
    if (!ensureConfirmDialog()) {
        return false;
    }

    const settings = {
        badge: options.badge || "删除确认",
        title: options.title || "确认删除？",
        message: options.message || "删除后将无法恢复。",
        acceptLabel: options.acceptLabel || "确认删除",
        cancelLabel: options.cancelLabel || "取消",
    };

    if (confirmBadge) {
        confirmBadge.textContent = settings.badge;
    }
    if (confirmTitle) {
        confirmTitle.textContent = settings.title;
    }
    if (confirmMessage) {
        confirmMessage.textContent = settings.message;
    }
    if (confirmAcceptButton) {
        confirmAcceptButton.textContent = settings.acceptLabel;
    }
    if (confirmCancelButton) {
        confirmCancelButton.textContent = settings.cancelLabel;
    }
    return true;
}

function requestDeleteConfirmation(options = {}) {
    if (!ensureConfirmDialog()) {
        return Promise.resolve(false);
    }
    configureConfirmDialog(options);

    if (confirmResolver) {
        return Promise.resolve(false);
    }

    confirmReturnFocus = document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;

    confirmOverlay.hidden = false;
    document.body.classList.add("modal-open");
    confirmAcceptButton.focus();

    return new Promise((resolve) => {
        confirmResolver = resolve;
    });
}

async function deleteHistoryRecord(recordId) {
    if (!recordId) {
        return;
    }
    const confirmed = await requestDeleteConfirmation({
        badge: "删除历史",
        title: "删除这条历史记录？",
        message: "删除后将无法恢复，这条问答记录会从当前账号的本地历史中移除。",
        acceptLabel: "确认删除",
        cancelLabel: "取消",
    });
    if (!confirmed) {
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

async function deleteMaterialFile(path, name) {
    const cleanPath = (path || "").trim();
    if (!cleanPath) {
        return;
    }

    const fileName = (name || cleanPath.split(/[\\/]/).pop() || cleanPath).trim();
    const confirmed = await requestDeleteConfirmation({
        badge: "删除文件",
        title: `删除 ${fileName}？`,
        message: "文件删除后会从资料目录移除，并立即重建知识库索引。这个操作无法撤销。",
        acceptLabel: "确认删除",
        cancelLabel: "取消",
    });
    if (!confirmed) {
        return;
    }

    try {
        const response = await fetch("/api/files", {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: cleanPath }),
        });
        const payload = await response.json();
        if (response.status === 401) {
            redirectToLogin();
            return;
        }
        if (!response.ok || !payload.deleted) {
            showToast(payload.message || "删除失败，请稍后重试。", "error");
            return;
        }

        updateStats(payload.stats);
        await loadFilesList();
        showToast(payload.message || `已删除：${fileName}`, "success");
    } catch (error) {
        showToast("删除失败，请稍后重试。", "error");
    }
}

async function uploadMaterials(files) {
    if (!uploadButton || !uploadInput || !files.length) {
        return;
    }

    uploadButton.disabled = true;
    uploadButton.textContent = "上传中";

    try {
        const formData = new FormData();
        for (const file of files) {
            formData.append("files", file);
        }

        const response = await fetch("/api/upload", {
            method: "POST",
            body: formData,
        });
        if (response.status === 401) {
            redirectToLogin();
            return;
        }

        const payload = await response.json();
        if (!response.ok || !payload.uploaded) {
            showToast(payload.message || "上传失败，请稍后重试。", "error");
            return;
        }

        updateStats(payload.stats);
        await loadFilesList();
        const uploadedNames = Array.isArray(payload.files) ? payload.files.join("、") : "";
        showToast(uploadedNames ? `上传成功：${uploadedNames}` : payload.message, "success");
    } catch (error) {
        showToast("上传失败，请检查文件类型或稍后重试。", "error");
    } finally {
        uploadButton.disabled = false;
        uploadButton.textContent = "上传资料";
        uploadInput.value = "";
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

wireConfirmDialog();

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
        await checkStartupStatus();
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

if (uploadButton && uploadInput) {
    uploadButton.addEventListener("click", () => {
        uploadInput.click();
    });

    uploadInput.addEventListener("change", async () => {
        const files = Array.from(uploadInput.files || []);
        await uploadMaterials(files);
    });
}

if (filesButton) {
    filesButton.addEventListener("click", async () => {
        await openFilesPanel();
    });
}

if (filesCloseButton) {
    filesCloseButton.addEventListener("click", () => {
        closeFilesPanel();
    });
}

if (filesOverlay) {
    filesOverlay.addEventListener("click", (event) => {
        if (event.target === filesOverlay) {
            closeFilesPanel();
        }
    });
}

if (filesList) {
    filesList.addEventListener("click", async (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
            return;
        }
        const button = target.closest(".file-delete-button");
        if (!button) {
            return;
        }
        const filePath = button.dataset.filePath || "";
        const fileName = button.dataset.fileName || "";
        await deleteMaterialFile(filePath, fileName);
    });
}

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

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && confirmResolver) {
        event.preventDefault();
        closeConfirmDialog(false);
        return;
    }
    if (event.key === "Escape" && filesOverlay && !filesOverlay.hidden) {
        event.preventDefault();
        closeFilesPanel();
    }
});

autoResizeComposer();
setStartupBlocked(startupBlocked);

refreshAuthState();






