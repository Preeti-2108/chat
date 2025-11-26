import asyncio
from src.helpers.conversation_builder import conversation_builder

# You can replace this with your actual async DB update logic
async def update_title_in_db_async(conversation_id: str, new_title: str):
    """
    Update the conversation title in your DB/storage asynchronously.
    """
    # Example: await dynamodb_client.update_item(...)
    # Simulate async DB call
    await asyncio.sleep(0.01)


def schedule_title_update(conversation_id: str, user_query: str, llm):
    """
    Schedules an async LLM title update for a conversation.
    Keeps handler code clean by wrapping trigger and callback.
    """
    asyncio.create_task(
        conversation_builder.async_update_title_with_llm(
            conversation_id,
            user_query,
            llm,
            update_title_in_db_async
        )
    )
