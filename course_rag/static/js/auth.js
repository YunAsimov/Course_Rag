const authForm = document.getElementById("auth-form");
const authUsernameInput = document.getElementById("auth-username");
const authPasswordInput = document.getElementById("auth-password");
const loginButton = document.getElementById("login-button");
const authBadge = document.getElementById("auth-badge");
const authStatus = document.getElementById("auth-status");

let startupBlocked = authForm?.dataset.indexing === "true";
let startupPollTimer = null;

function setAuthStatus(message, tone = "muted") {
    authStatus.textContent = message;
    authStatus.classList.remove("is-error", "is-success", "is-info");
    if (tone === "error") {
        authStatus.classList.add("is-error");
    }
    if (tone === "success") {
        authStatus.classList.add("is-success");
    }
    if (tone === "info") {
        authStatus.classList.add("is-info");
    }
}

function setAuthControlsDisabled(disabled) {
    authUsernameInput.disabled = disabled;
    authPasswordInput.disabled = disabled;
    loginButton.disabled = disabled;
}

function setAuthBusy(isBusy, loginLabel = "登录") {
    loginButton.disabled = isBusy || startupBlocked;
    loginButton.textContent = loginLabel;
}

function setStartupState(indexing, message = "") {
    startupBlocked = indexing;
    authBadge.textContent = indexing ? "构建中" : "未登录";
    setAuthControlsDisabled(indexing);
    if (indexing) {
        setAuthStatus(message || "知识库索引构建中，预计需要 1 分钟左右。索引完成后即可登录。", "info");
        scheduleStartupPoll();
    } else {
        clearStartupPoll();
        setAuthStatus("请输入用户名和密码登录。若需新增账号，请联系管理员处理。", "muted");
    }
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

function redirectToApp() {
    window.location.replace("/");
}

async function submitAuth(endpoint, loginLabel) {
    if (startupBlocked) {
        setAuthStatus("知识库仍在构建中，请稍候再登录。", "info");
        return;
    }

    const username = authUsernameInput.value.trim();
    const password = authPasswordInput.value;

    if (!username || !password) {
        setAuthStatus("请输入用户名和密码。", "error");
        return;
    }

    setAuthBusy(true, loginLabel);
    try {
        const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password }),
        });
        const payload = await response.json();
        if (!response.ok || !payload.authenticated) {
            setAuthStatus(payload.message || "认证失败。", "error");
            return;
        }

        authBadge.textContent = payload.username || username;
        authBadge.classList.add("is-authenticated");
        setAuthStatus(payload.message || "认证成功，正在跳转到问答页。", "success");
        authPasswordInput.value = "";
        redirectToApp();
    } catch (error) {
        setAuthStatus("认证请求失败，请检查本地服务是否正常运行。", "error");
    } finally {
        setAuthBusy(false);
    }
}

async function checkStartupStatus() {
    try {
        const response = await fetch("/api/health");
        const payload = await response.json();
        const indexing = Boolean(payload.indexing) || payload.status === "indexing";
        setStartupState(indexing, payload.message || "");
    } catch (error) {
        setStartupState(true, "服务正在启动并构建知识库，请稍候重试。");
    }
}

async function checkExistingSession() {
    try {
        const response = await fetch("/api/auth/me");
        const payload = await response.json();
        if (response.ok && payload.authenticated) {
            redirectToApp();
        }
    } catch (error) {
        setAuthStatus("无法读取登录状态，请稍后重试。", "error");
    }
}

authForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitAuth("/api/auth/login", "登录中");
});

if (startupBlocked) {
    setStartupState(true, authStatus.textContent.trim());
} else {
    setStartupState(false);
}

checkExistingSession();
checkStartupStatus();
