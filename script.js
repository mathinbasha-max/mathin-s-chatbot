// =========================================================
// CHAT FUNCTION
// =========================================================

async function sendMessage() {

    const input = document.getElementById("message");
    const chat = document.getElementById("chat");

    const message = input.value.trim();

    if (!message) {
        return;
    }


    // Show user message

    chat.innerHTML += `
        <div class="message user-message">
            <div class="message-content">
                ${message}
            </div>
        </div>
    `;


    input.value = "";

    chat.scrollTop = chat.scrollHeight;


    try {

        const response = await fetch("/chat", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                message: message
            })

        });


        const data = await response.json();


        // Show AI response

        chat.innerHTML += `
            <div class="message bot-message">
                <div class="message-content">
                    ${data.reply}
                </div>
            </div>
        `;


        chat.scrollTop = chat.scrollHeight;


    } catch (error) {

        console.error(
            "Chat error:",
            error
        );


        chat.innerHTML += `
            <div class="message bot-message">
                <div class="message-content">
                    ❌ Unable to connect to AI server.
                </div>
            </div>
        `;

    }

}


// =========================================================
// ENTER KEY
// =========================================================

const messageInput =
    document.getElementById("message");


if (messageInput) {

    messageInput.addEventListener(
        "keydown",
        function(event) {

            if (event.key === "Enter") {

                event.preventDefault();

                sendMessage();

            }

        }
    );

}


// =========================================================
// REQUEST NOTIFICATION PERMISSION
// =========================================================

async function requestNotificationPermission() {

    if (!("Notification" in window)) {

        console.log(
            "Browser notifications are not supported."
        );

        return;

    }


    if (Notification.permission === "default") {

        try {

            await Notification.requestPermission();

        } catch (error) {

            console.log(
                "Notification permission error:",
                error
            );

        }

    }

}


// =========================================================
// SHOW BROWSER NOTIFICATION
// =========================================================

function showReminderNotification(
    reminder
) {

    if (!("Notification" in window)) {
        return;
    }


    if (Notification.permission !== "granted") {
        return;
    }


    const title =
        "⏰ Reminder";


    const body =
        reminder.text ||
        "You have a reminder.";


    try {

        const notification =
            new Notification(
                title,
                {
                    body: body,
                    icon: "/favicon.ico"
                }
            );


        notification.onclick =
            function() {

                window.focus();

                notification.close();

            };


    } catch (error) {

        console.log(
            "Notification error:",
            error
        );

    }

}


// =========================================================
// CHECK DUE REMINDERS
// =========================================================

async function checkReminders() {

    try {

        const response =
            await fetch(
                "/check-reminders"
            );


        if (!response.ok) {

            console.log(
                "Reminder checker failed."
            );

            return;

        }


        const data =
            await response.json();


        if (!data.success) {

            console.log(
                "Reminder checker returned an error."
            );

            return;

        }


        const reminders =
            data.reminders || [];


        if (reminders.length === 0) {

            return;

        }


        // Process each due reminder

        for (
            const reminder of reminders
        ) {

            // Show notification

            showReminderNotification(
                reminder
            );


            // Tell backend that notification
            // has been processed

            try {

                await fetch(
                    `/mark-notification-sent/${reminder.id}`,
                    {
                        method: "POST"
                    }
                );

            } catch (error) {

                console.log(
                    "Could not mark reminder:",
                    error
                );

            }

        }

    } catch (error) {

        console.log(
            "Reminder check error:",
            error
        );

    }

}


// =========================================================
// START REMINDER SYSTEM
// =========================================================

async function startReminderSystem() {

    // Ask user for notification permission

    await requestNotificationPermission();


    // Check immediately

    await checkReminders();


    // Check every 30 seconds

    setInterval(
        checkReminders,
        30000
    );

}


// =========================================================
// START
// =========================================================

startReminderSystem();
