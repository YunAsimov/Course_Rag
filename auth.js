const authForm = document.getElementById("auth-form");
const authUsernameInput = document.getElementById("auth-username");
const authPasswordInput = document.getElementById("auth-password");
const loginButton = document.getElementById("login-button");
const registerButton = document.getElementById("register-button");
const authBadge = document.getElementById("auth-badge");
const authStatus = document.getElementById("auth-status");

function setAuthStatus(message, tone = "muted") {
    authStatus.textContent = message;
    authStatus.classList.remove("is-error", "is-success");
    if (tone === "error") {
        authStatus.classList.add("is-error");
    }
    if (tone === "success") {
        authStatus.classList.add("is-success");
    }
}

function setAuthBusy(isBusy, loginLabel = "登录", registerLabel = "注册") {
    loginButton.disabled = isBusy;
    if (registerButton) {
        registerButton.disabled = isBusy;
    }
    loginButton.textContent = loginLabel;
    if (registerButton) {
        registerButton.textContent = registerLabel;
    }
}

function redirectToApp() {
    window.location.replace("/");
}

async function submitAuth(endpoint, loginLabel, registerLabel) {
    const username = authUsernameInput.value.trim();
    const password = authPasswordInput.value;

    if (!username || !password) {
        setAuthStatus("请输入用户名和密码。", "error");
        return;
    }

    setAuthBusy(true, loginLabel, registerLabel);
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
    await submitAuth("/api/auth/login", "登录中", "注册");
});

if (registerButton) {
    registerButton.addEventListener("click", async () => {
        await submitAuth("/api/auth/register", "登录", "注册中");
    });
}

checkExistingSession();
