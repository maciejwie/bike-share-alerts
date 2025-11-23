export default {
    async fetch(request, env, ctx) {
        return new Response('Cron worker - check logs for scheduled execution', { status: 200 });
    },

    async scheduled(event, env, ctx) {
        try {
            const response = await fetch('https://bike-share-alerts-collector.vercel.app/api/collector', {
                headers: {
                    'Authorization': `Bearer ${env.CRON_SECRET}`
                }
            });

            const responseText = await response.text();
        } catch (error) {
            console.error(`Error triggering collector: ${error.message}`);
            console.error(`Stack: ${error.stack}`);
        }
    }
}
