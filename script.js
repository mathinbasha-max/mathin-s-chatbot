
const input = document.getElementById("message");
const chat = document.getElementById("chat");
const sendButton = document.getElementById("sendButton");
const enableNotificationsButton =
    document.getElementById("enableNotifications");
const notificationStatus =
    document.getElementById("notificationStatus");

let reminderCheckRunning = false;

// Safely display chat text
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

// Send chat message
async function sendMessage() {
    const message = input.value.trim();

    if (!message) return;

    addMessage(message, "user");
    input.value = "";
    sendButton.disabled = true;

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Chat request failed");
        }

        addMessage(data.reply || "No reply received.", "bot");
    } catch (error) {
        console.error("Chat error:", error);
        addMessage(
            "❌ Unable to connect to AI server. Please try again.",
            "bot"
        );
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

// Enable browser notifications after a user click
enableNotificationsButton.addEventListener("click", async () => {
    if (!("Notification" in window)) {
        notificationStatus.textContent =
            "This browser does not support notifications.";
        return;
    }

    try {
        const permission = await Notification.requestPermission();

        if (permission === "granted") {
            notificationStatus.textContent =
                "✅ Notifications enabled!";
            enableNotificationsButton.textContent =
                "✅ Notifications Enabled";
            await checkReminders();
        } else {
            notificationStatus.textContent =
                "Notifications blocked. Allow them in browser site settings.";
        }
    } catch (error) {
        console.error("Permission error:", error);
        notificationStatus.textContent =
            "Could not enable notifications.";
    }
});

// Display one reminder notification
function showReminderNotification(reminder) {
    if (!("Notification" in window)) return false;
    if (Notification.permission !== "granted") return false;

    try {
        const notification = new Notification("⏰ My AI Chatbot Reminder", {
            body: reminder.text || "You have a reminder."
        });

        notification.onclick = () => {
            window.focus();
            notification.close();
        };

        return true;
    } catch (error) {
        console.error("Notification error:", error);
        return false;
    }
}

// Check due reminders on the backend
async function checkReminders() {
    if (reminderCheckRunning) return;
    reminderCheckRunning = true;

    try {
        const response = await fetch("/check-reminders", {
            cache: "no-store"
        });

        if (!response.ok) {
            throw new Error("Reminder check failed");
        }

        const data = await response.json();

        if (!data.success) return;

        for (const reminder of (data.reminders || [])) {
            // Do not mark as sent if permission is missing
            const sent = showReminderNotification(reminder);

            if (!sent) continue;

            const markResponse = await fetch(
                `/mark-notification-sent/${reminder.id}`,
                { method: "POST" }
            );

            if (!markResponse.ok) {
                console.error(
                    "Could not mark reminder as sent:",
                    reminder.id
                );
            }
        }
    } catch (error) {
        console.error("Reminder check error:", error);
    } finally {
        reminderCheckRunning = false;
    }
}

// Start checking reminders while the page is open
if ("Notification" in window &&
    Notification.permission === "granted") {
    notificationStatus.textContent = "✅ Notifications are enabled.";
}

checkReminders();
setInterval(checkReminders, 30000);
