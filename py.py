import discord
from discord.ext import commands, tasks
import random
import sqlite3

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# SQLite 데이터베이스 연결
conn = sqlite3.connect('fishing_bot.db')
c = conn.cursor()

# 테이블 생성 (최초 실행 시 필요)
c.execute('''CREATE TABLE IF NOT EXISTS users (server_id INTEGER, user_id INTEGER, balance INTEGER, fish_count INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS fish (name TEXT, rarity TEXT, value INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS fishing_spots (server_id INTEGER, owner_id INTEGER, price INTEGER)''')
conn.commit()

# 초기 물고기 종류 삽입
fish_data = [
    ('Common Fish', 'common', 10),
    ('Rare Fish', 'rare', 50),
    ('Epic Fish', 'epic', 100),
    ('Legendary Fish', 'legendary', 500),
    ('Mystic Fish', 'mythical', 1000)
]
c.executemany("INSERT OR IGNORE INTO fish (name, rarity, value) VALUES (?, ?, ?)", fish_data)
conn.commit()

# 유저 정보 가져오기
def get_user(server_id, user_id):
    c.execute("SELECT * FROM users WHERE server_id = ? AND user_id = ?", (server_id, user_id))
    result = c.fetchone()
    if result is None:
        c.execute("INSERT INTO users (server_id, user_id, balance, fish_count) VALUES (?, ?, 0, 0)", (server_id, user_id))
        conn.commit()
        return (server_id, user_id, 0, 0)
    return result

# 낚시 명령어
@bot.command()
async def 낚시(ctx):
    user = get_user(ctx.guild.id, ctx.author.id)
    c.execute("SELECT * FROM fish ORDER BY RANDOM() LIMIT 1")
    fish = c.fetchone()
    
    if fish:
        fish_name, rarity, value = fish
        new_balance = user[2] + value
        new_fish_count = user[3] + 1
        c.execute("UPDATE users SET balance = ?, fish_count = ? WHERE server_id = ? AND user_id = ?", 
                  (new_balance, new_fish_count, ctx.guild.id, ctx.author.id))
        conn.commit()
        
        embed = discord.Embed(title="🎣 낚시 결과", color=discord.Color.blue())
        embed.add_field(name="물고기 종류", value=f"{fish_name} ({rarity.capitalize()})", inline=False)
        embed.add_field(name="획득한 금액", value=f"{value} 코인", inline=False)
        embed.add_field(name="총 잔액", value=f"{new_balance} 코인", inline=False)
        embed.set_footer(text=f"{ctx.author.display_name}님의 낚시 결과")
        await ctx.send(embed=embed)
    else:
        await ctx.send("낚시에 실패했습니다. 다시 시도해보세요!")

# 잔액 확인
@bot.command()
async def 잔액(ctx):
    user = get_user(ctx.guild.id, ctx.author.id)
    embed = discord.Embed(title="💰 잔액 확인", description=f"{ctx.author.mention}님의 현재 잔액은 {user[2]} 코인입니다.", color=discord.Color.green())
    await ctx.send(embed=embed)

# 랭킹 시스템
@bot.command()
async def 랭킹(ctx):
    c.execute("SELECT user_id, balance FROM users WHERE server_id = ? ORDER BY balance DESC LIMIT 10", (ctx.guild.id,))
    rankings = c.fetchall()
    embed = discord.Embed(title=f"🏆 {ctx.guild.name} 낚시 랭킹", color=discord.Color.gold())
    
    for i, (user_id, balance) in enumerate(rankings, 1):
        user = await bot.fetch_user(user_id)
        embed.add_field(name=f"{i}위", value=f"{user.display_name}: {balance} 코인", inline=False)
    
    await ctx.send(embed=embed)

# 낚시터 매입 및 매각
@bot.command()
async def 낚시터(ctx, action: str):
    user = get_user(ctx.guild.id, ctx.author.id)
    if action == "매입":
        # 예시: 매입 가격 1000 코인
        if user[2] >= 1000:
            c.execute("INSERT INTO fishing_spots (server_id, owner_id, price) VALUES (?, ?, 1000)", (ctx.guild.id, ctx.author.id))
            c.execute("UPDATE users SET balance = ? WHERE server_id = ? AND user_id = ?", 
                      (user[2] - 1000, ctx.guild.id, ctx.author.id))
            conn.commit()
            embed = discord.Embed(title="🏞 낚시터 매입", description=f"{ctx.author.mention}님이 낚시터를 매입했습니다!", color=discord.Color.blue())
            await ctx.send(embed=embed)
        else:
            await ctx.send("코인이 부족합니다.")
    elif action == "매각":
        c.execute("SELECT price FROM fishing_spots WHERE server_id = ? AND owner_id = ?", (ctx.guild.id, ctx.author.id))
        result = c.fetchone()
        if result:
            sale_price = int(result[0] * 0.8)  # 매각 시 원래 값의 80%
            c.execute("DELETE FROM fishing_spots WHERE server_id = ? AND owner_id = ?", (ctx.guild.id, ctx.author.id))
            c.execute("UPDATE users SET balance = ? WHERE server_id = ? AND user_id = ?", 
                      (user[2] + sale_price, ctx.guild.id, ctx.author.id))
            conn.commit()
            embed = discord.Embed(title="🏞 낚시터 매각", description=f"{ctx.author.mention}님이 낚시터를 매각했습니다! (+{sale_price} 코인)", color=discord.Color.red())
            await ctx.send(embed=embed)
        else:
            await ctx.send("소유한 낚시터가 없습니다.")
    else:
        await ctx.send("명령어가 올바르지 않습니다. '!낚시터 매입' 또는 '!낚시터 매각'을 사용하세요.")

# 이벤트 시스템
@tasks.loop(hours=72)
async def 이벤트():
    for guild in bot.guilds:
        channel = discord.utils.get(guild.text_channels, name="낚시")
        if channel:
            embed = discord.Embed(title="🎉 이벤트 알림", description="특별한 물고기가 등장했습니다! 지금 낚시에 도전하세요!", color=discord.Color.purple())
            await channel.send(embed=embed)

# 에러 처리
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("존재하지 않는 명령어입니다. 도움말을 확인하세요.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("명령어의 인수가 부족합니다. 다시 시도해 주세요.")
    else:
        await ctx.send("알 수 없는 에러가 발생했습니다.")
        print(error)

# 봇 시작 및 이벤트 초기화
@bot.event
async def on_ready():
    이벤트.start()
    print("봇이 준비되었습니다.")

bot.run('MTMwMTgzMjQxMjk3OTkyMDkyOA.GmL0aU.CLmAOclTnTZ4tz7LVtvRKznUnv0ZgUrZUFO01I')
