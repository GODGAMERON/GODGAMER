# Telegram SMM Automation Bot

## Railway deployment
1. Upload/extract this project into your GitHub repository.
2. Connect the repository to Railway as a Worker service.
3. Add a Railway PostgreSQL service and set `DATABASE_URL` in the worker variables.
4. Set `BOT_TOKEN` and `OWNER_ID`.
5. Deploy using the included `Procfile`.
6. Make the bot an administrator in each channel it should monitor.

Do not commit a real `.env` file or API keys.

## Per-service quantity
Assign a panel service with `/SERVICEID @channel PanelName SERVICE_ID`, then set its quantity with `/setserviceqty @channel SERVICE_ID QUANTITY`. Each assigned service receives its own order for each new channel post. Pending orders do not block later posts.

Newly registered channels are created active with automation enabled. The bot must be a channel administrator to receive channel posts.
