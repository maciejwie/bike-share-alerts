export default {
    async fetch(request, env, ctx) {
        return new Response('Cron worker - check logs for scheduled execution', { status: 200 });
    },

    async scheduled(event, env, ctx) {
        try {
            const response = await fetch('https://bike-share-alerts-collector.vercel.app/api/collector', {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${env.CRON_SECRET}`
                }
            });

            if (!response.ok) {
                console.error(`Collector returned ${response.status}: ${await response.text()}`);
                return;
            }

            const responseText = await response.text();
            console.log(`Collector response: ${responseText}`);
        } catch (error) {
            console.error(`Error triggering collector: ${error.message}`);
            console.error(`Stack: ${error.stack}`);
        }
    }
}
