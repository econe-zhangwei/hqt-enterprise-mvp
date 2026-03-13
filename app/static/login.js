(function () {
  const loginBtn = document.getElementById("loginBtn");
  const msgEl = document.getElementById("loginMsg");
  const usernameEl = document.getElementById("username");
  const passwordEl = document.getElementById("password");

  const existing = localStorage.getItem("hqt_token");
  if (existing) {
    window.location.href = "/static/workspace.html";
  }

  async function login() {
    loginBtn.disabled = true;
    msgEl.textContent = "登录中...";

    try {
      const resp = await fetch("/api/v1/auth/password/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: usernameEl.value.trim(),
          password: passwordEl.value,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "登录失败");

      localStorage.setItem("hqt_token", data.data.token);
      localStorage.setItem("hqt_user", data.data.subject);
      msgEl.textContent = "登录成功，正在跳转...";
      setTimeout(() => {
        window.location.href = "/static/workspace.html";
      }, 300);
    } catch (err) {
      msgEl.textContent = err.message || "登录失败";
    } finally {
      loginBtn.disabled = false;
    }
  }

  loginBtn.addEventListener("click", login);
  passwordEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") login();
  });
})();
