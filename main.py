import os
import discord
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from agent import agent_app

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    user_id = str(message.author.id)
    user_text = message.content
    async with message.channel.typing():
        config = {'configurable': {'thread_id': user_id}}
        result = await agent_app.ainvoke(
            {'messages': [HumanMessage(content=user_text)]},
            config=config
        )
        final_reply = result['messages'][-1].content
        await message.channel.send(final_reply)

        if os.path.exists('chart.png'):
            await message.channel.send(file=discord.File('chart.png'))
            os.remove('chart.png')

client.run(os.getenv('DISCORD_TOKEN'))
