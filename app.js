const chatFeed = document.getElementById("chat-feed");
const sourceList = document.getElementById("source-list");
const sourceCount = document.getElementById("source-count");
const askForm = document.getElementById("ask-form");
const input = document.getElementById("question-input");
const submitButton = document.getElementById("submit-button");

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

    for (let index = 0; index < mathSpans.length; index += 1) {
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

function appendMessage(role, content, mode = "") {
    const article = document.createElement("article");
    article.className = `message ${role}`;

    const modeLabel = mode || role;
    const renderedBody = role === "assistant"
        ? renderMarkdown(content)
        : `<p>${escapeHtml(content)}</p>`;
    article.innerHTML = `
        <div class="message-head">
            <span class="speaker">${role === "user" ? "你" : "知识助手"}</span>
            <span class="mode-badge">${escapeHtml(modeLabel)}</span>
        </div>
        <div class="message-body markdown-body">${renderedBody}</div>
    `;
    chatFeed.appendChild(article);
    chatFeed.scrollTop = chatFeed.scrollHeight;
    return article;
}

function renderSources(sources) {
    sourceCount.textContent = String(sources.length);
    sourceList.innerHTML = "";

    if (!sources.length) {
        sourceList.innerHTML = `<p class="empty-state">这次回答没有命中可展示的来源片段。</p>`;
        return;
    }

    for (const source of sources) {
        const wrapper = document.createElement("article");
        wrapper.className = "source-item";
        const sourceHref = buildSourceHref(source);
        const pageLabel = source.page_number ? `p.${source.page_number}` : "";
        const sectionLabel = source.section_heading || source.page_heading || "";
        const sourceSnippet = normalizeSourceSnippet(source.snippet || "");
        wrapper.innerHTML = `
            <div class="source-meta">
                <span class="source-score">score ${source.score}</span>
                ${pageLabel ? `<span class="source-page">${escapeHtml(pageLabel)}</span>` : ""}
            </div>
            <h3 class="source-title">
                ${sourceHref
                    ? `<a class="source-link" href="${escapeAttr(sourceHref)}" target="_blank" rel="noreferrer">${escapeHtml(source.title)}</a>`
                    : escapeHtml(source.title)}
            </h3>
            ${sectionLabel ? `<div class="source-heading">${escapeHtml(sectionLabel)}</div>` : ""}
            <div class="source-path">
                ${sourceHref
                    ? `<a class="source-link source-path-link" href="${escapeAttr(sourceHref)}" target="_blank" rel="noreferrer">${escapeHtml(source.path)}</a>`
                    : escapeHtml(source.path)}
            </div>
            <div class="source-snippet markdown-body">${renderMarkdown(sourceSnippet)}</div>
        `;
        sourceList.appendChild(wrapper);
    }
}

async function ask(question) {
    const trimmed = question.trim();
    if (!trimmed) {
        return;
    }

    appendMessage("user", trimmed, "question");
    const loadingMessage = appendMessage("assistant", "正在检索资料并整理回答...", "loading");

    submitButton.disabled = true;
    submitButton.textContent = "检索中";

    try {
        const response = await fetch("/api/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question: trimmed }),
        });
        const payload = await response.json();
        loadingMessage.remove();
        appendMessage("assistant", payload.answer, payload.mode);
        renderSources(payload.sources || []);
    } catch (error) {
        loadingMessage.remove();
        appendMessage("assistant", "请求失败，请检查后端是否正常运行。", "error");
        renderSources([]);
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = "发送";
        chatFeed.scrollTop = chatFeed.scrollHeight;
    }
}

askForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = input.value;
    input.value = "";
    await ask(question);
});

for (const button of document.querySelectorAll(".suggestion-chip")) {
    button.addEventListener("click", async () => {
        input.value = button.dataset.question;
        await ask(button.dataset.question);
    });
}
