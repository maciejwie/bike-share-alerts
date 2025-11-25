export default {
    async fetch(request, env, ctx) {
        return new Response('Cron worker - check logs for scheduled execution', { status: 200 });
    },

    async scheduled(event, env, ctx) {
        try {
            let urls = [];
            try {
                urls = JSON.parse(env.HEARTBEAT_URLS || '[]');
            } catch (e) {
                console.error(`Failed to parse HEARTBEAT_URLS: ${e.message}`);
                return;
            }

            if (!urls.length) {
                console.log('No HEARTBEAT_URLS configured.');
                return;
            }

            console.log(`Triggering heartbeats for ${urls.length} services...`);

            const results = await Promise.allSettled(urls.map(url =>
                fetch(url, {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${env.CRON_SECRET}`
                    }
                })
            ));

            results.forEach((result, index) => {
                const url = urls[index];
                if (result.status === 'fulfilled') {
                    const response = result.value;
                    if (response.ok) {
                        console.log(`[SUCCESS] ${url}: ${response.status}`);
                    } else {
                        console.error(`[FAILURE] ${url}: ${response.status} - ${response.statusText}`);
                    }
                } else {
                    console.error(`[ERROR] ${url}: ${result.reason}`);
                }
            });

        } catch (error) {
            console.error(`Error in scheduled task: ${error.message}`);
            console.error(`Stack: ${error.stack}`);
        }
    }
}
