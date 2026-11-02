const input = document.getElementById("message");
const chat = document.getElementById("chat");
const sendButton = document.getElementById("sendButton");
const enableNotificationsButton = document.getElementById("enableNotifications");
const notificationStatus = document.getElementById("notificationStatus");

function addMessage(text, type) {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${type}-message`;
    const content = document.createElement("div");
    content.className = "message-content";
    content.textContent = text;
    wrapper.appendChild(content);
    chat.appendChild(wrapper);
    chat.scrollTop = chat.scrollHeight;
}

async function sendMessage() {
    const message = input.value.trim();
    if (!message) return;

    addMessage(message, "user");
    input.value = "";
    sendButton.disabled = true;

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({message})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Chat request failed");
        addMessage(data.reply || "No reply received.", "bot");
    } catch (error) {
        console.error("Chat error:", error);
        addMessage("❌ Unable to connect to AI server. Please try again.", "bot");
    } finally {
        sendButton.disabled = false;
        input.focus();
    }
}

sendButton.addEventListener("click", sendMessage);
input.addEventListener("keydown", event => {
    if (event.key === "Enter") {
        event.preventDefault();
        sendMessage();
    }
});

function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    const rawData = atob(base64);
    return Uint8Array.from([...rawData].map(char => char.charCodeAt(0)));
}

async function enablePushNotifications() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
        notificationStatus.textContent = "This browser does not support web push notifications.";
        return;
    }

    enableNotificationsButton.disabled = true;
    try {
        const permission = await Notification.requestPermission();
        if (permission !== "granted") {
            notificationStatus.textContent = "Notifications are blocked. Allow them in browser site settings and try again.";
            return;
        }

        const registration = await navigator.serviceWorker.register("/service-worker.js");
        await navigator.serviceWorker.ready;

        const keyResponse = await fetch("/vapid-public-key", {cache: "no-store"});
        const keyData = await keyResponse.json();
        if (!keyResponse.ok || !keyData.success || !keyData.publicKey) {
            throw new Error(keyData.error || "VAPID public key is missing on the server.");
        }

        let subscription = await registration.pushManager.getSubscription();
        if (!subscription) {
            subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(keyData.publicKey)
            });
        }

        const saveResponse = await fetch("/subscribe", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({subscription: subscription.toJSON()})
        });
        const saveData = await saveResponse.json();

        if (!saveResponse.ok || !saveData.success) {
            throw new Error(saveData.error || "Could not save subscription.");
        }

        notificationStatus.textContent = "✅ Push notifications enabled. You can close this page after setting a reminder.";
        enableNotificationsButton.textContent = "✅ Reminders Enabled";
    } catch (error) {
        console.error("Enable push error:", error);
        notificationStatus.textContent = "❌ Could not enable push notifications: " + error.message;
    } finally {
        enableNotificationsButton.disabled = false;
    }
}

enableNotificationsButton.addEventListener("click", enablePushNotifications);

if ("serviceWorker" in navigator && "Notification" in window && Notification.permission === "granted") {
    notificationStatus.textContent = "Notifications permission is allowed. Click Enable Reminders if you haven't subscribed this browser yet.";
}
