"""
HALOS Payment Webhook Server
Runs alongside the main bot to handle Click payment webhooks
"""
import os
import asyncio
import logging
from aiohttp import web

from app.payment_webhook import handle_click_webhook
from app.database import get_database

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Webhook server port (Railway assigns PORT env var)
PORT = int(os.getenv("WEBHOOK_PORT", os.getenv("PORT", "8080")))


async def click_webhook_handler(request: web.Request) -> web.Response:
    """Handle Click payment webhook requests"""
    try:
        # Get request data
        data = await request.post()
        data_dict = dict(data)
        
        logger.info(f"Click webhook received: {data_dict}")
        
        # Process webhook
        result = await handle_click_webhook(data_dict)
        
        logger.info(f"Click webhook response: {result}")
        
        return web.json_response(result)
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.json_response({"error": -8, "error_note": str(e)})


async def click_prepare_handler(request: web.Request) -> web.Response:
    """Handle Click PREPARE request (action=0)"""
    try:
        data = await request.post()
        data_dict = dict(data)
        data_dict['action'] = 0  # Force prepare action
        
        logger.info(f"Click PREPARE received: {data_dict}")
        
        result = await handle_click_webhook(data_dict)
        
        logger.info(f"Click PREPARE response: {result}")
        
        return web.json_response(result)
        
    except Exception as e:
        logger.error(f"Click prepare error: {e}")
        return web.json_response({"error": -8, "error_note": str(e)})


async def click_complete_handler(request: web.Request) -> web.Response:
    """Handle Click COMPLETE request (action=1)"""
    try:
        data = await request.post()
        data_dict = dict(data)
        data_dict['action'] = 1  # Force complete action
        
        logger.info(f"Click COMPLETE received: {data_dict}")
        
        result = await handle_click_webhook(data_dict)
        
        logger.info(f"Click COMPLETE response: {result}")
        
        return web.json_response(result)
        
    except Exception as e:
        logger.error(f"Click complete error: {e}")
        return web.json_response({"error": -8, "error_note": str(e)})


async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint for Railway"""
    return web.Response(text="OK")


async def payment_status(request: web.Request) -> web.Response:
    """Check payment status by order_id"""
    try:
        order_id = request.match_info.get('order_id')
        
        if not order_id:
            return web.json_response({"error": "order_id required"})
        
        db = await get_database()
        
        # Parse order_id to get telegram_id
        parts = order_id.split('_')
        if len(parts) < 3:
            return web.json_response({"error": "Invalid order_id format"})
        
        telegram_id = int(parts[1])
        
        # Get user and payment info
        user = await db.get_user(telegram_id)
        if not user:
            return web.json_response({"error": "User not found"})
        
        # Get latest payment for this order
        payment = await db.fetch_one(
            "SELECT * FROM payments WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1" if db.is_postgres else
            "SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            user['id']
        )
        
        if payment:
            return web.json_response({
                "status": payment.get('status'),
                "plan_id": payment.get('plan_id'),
                "amount": payment.get('amount_uzs'),
                "created_at": str(payment.get('created_at')),
                "completed_at": str(payment.get('completed_at')) if payment.get('completed_at') else None
            })
        else:
            return web.json_response({"status": "not_found"})
            
    except Exception as e:
        logger.error(f"Payment status error: {e}")
        return web.json_response({"error": str(e)})


async def init_app() -> web.Application:
    """Initialize the webhook server"""
    app = web.Application()
    
    # Initialize database
    await get_database()
    
    # Routes
    app.router.add_post('/click/prepare', click_prepare_handler)  # Click Prepare URL
    app.router.add_post('/click/complete', click_complete_handler)  # Click Complete URL
    app.router.add_post('/click/webhook', click_webhook_handler)  # Generic webhook
    app.router.add_post('/click', click_webhook_handler)  # Alternative endpoint
    app.router.add_get('/health', health_check)
    app.router.add_get('/status/{order_id}', payment_status)
    app.router.add_get('/', health_check)  # Root health check
    
    logger.info(f"Webhook server initialized on port {PORT}")
    
    return app


async def start_webhook_server_async():
    """Start webhook server asynchronously (for running alongside bot)"""
    app = await init_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"Webhook server started on port {PORT}")
    return runner


def run_webhook_server():
    """Run the webhook server standalone"""
    logger.info(f"Starting webhook server on port {PORT}...")
    asyncio.run(start_webhook_server_async())
    # Keep running
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    run_webhook_server()
