import os
import discord
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from agent import agent_app


#載入金鑰
load_dotenv()

#Discord Bot前端通訊
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    user_id = str(message.author.id)
    user_text = message.content
    #機器人顯示輸入中
    async with message.channel.typing():
        #用Discord User ID當作記憶的key
        config = {'configurable': {'thread_id': user_id}}
        result = await agent_app.ainvoke(
            {'messages': [HumanMessage(content=user_text)]},
            config=config
        )
        #抓取LLM生的最後一句話回傳
        final_reply = result['messages'][-1].content
        await message.channel.send(final_reply)

        if os.path.exists('chart.png'):
            await message.channel.send(file=discord.File('chart.png'))
            os.remove('chart.png')

#啟動機器人
client.run(os.getenv('DISCORD_TOKEN'))
