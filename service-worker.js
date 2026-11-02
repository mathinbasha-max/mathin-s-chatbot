self.addEventListener("push", event => {
    let data = {};
    try {
        data = event.data ? event.data.json() : {};
    } catch (_) {
        data = {body: event.data ? event.data.text() : "You have a reminder."};
    }

    const title = data.title || "⏰ My AI Chatbot Reminder";
    const options = {
        body: data.body || "You have a reminder.",
        icon: "/icon-192.png",
        badge: "/icon-192.png",
        data: {url: data.url || "/"},
        tag: data.tag || "chatbot-reminder",
        renotify: false
    };

    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", event => {
    event.notification.close();
    const targetUrl = event.notification.data && event.notification.data.url
        ? event.notification.data.url
        : "/";

    event.waitUntil((async () => {
        const clientsList = await clients.matchAll({type: "window", includeUncontrolled: true});
        for (const client of clientsList) {
            if ("focus" in client) {
                await client.focus();
                return;
            }
        }
        if (clients.openWindow) await clients.openWindow(targetUrl);
    })());
});
