import discord
import asyncio
import os
import shutil
from discord.ext import commands
from concurrent.futures import ThreadPoolExecutor

# Import the logic from the pw-client core folder
# Ensure empty __init__.py exists in bot/ and bot/core/ for these imports to work
from bot.core.pw_utils.content import fetch_batches, fetch_notes, fetch_dpp
from bot.core.pw_utils.utils import verify_token

# Placeholder for your GDrive Logic (You need to implement the actual API calls)
# from bot.services.gdrive_service import upload_folder_to_drive 

class Extractor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Create a thread pool so downloads don't freeze the bot
        self.executor = ThreadPoolExecutor(max_workers=2)

    def run_extraction(self, token, user_id):
        """
        This function runs Sync (blocking) code.
        It mimics what streamlit.py was doing but headless.
        """
        base_path = f"storage/temp_{user_id}"
        os.makedirs(base_path, exist_ok=True)
        
        # 1. Verify Token
        valid = verify_token(token)
        if not valid.get("success"):
            return None, "Invalid Token"

        # 2. Fetch Batches
        batches = fetch_batches(token)
        if not batches:
            return None, "No batches found."

        # LIMITATION: For automation, you might need to extract ALL batches 
        # or ask the user to specify a batch slug. 
        # For this example, let's just grab the first batch found.
        target_batch = batches[0] 
        batch_slug = target_batch['slug']

        # 3. Download Logic (Simplified for brevity)
        # You would loop through subjects -> topics -> fetch_notes here
        # similar to how streamlit.py loops through them.
        
        # Fake example of downloading a file to local storage
        with open(f"{base_path}/report.txt", "w") as f:
            f.write(f"Extraction for batch {target_batch['name']} completed.")

        # 4. Upload to GDrive
        # drive_link = upload_folder_to_drive(base_path, folder_name=f"Extraction_{user_id}")
        drive_link = "https://drive.google.com/drive/folders/EXAMPLE_LINK"

        # 5. Cleanup local files
        # shutil.rmtree(base_path)

        return drive_link, None

    @commands.command(name="extract")
    async def extract(self, ctx, token: str = None):
        """
        Usage: !extract <session_token>
        WARNING: Do this in DMs to protect your token!
        """
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.message.delete() # Delete token from public chat immediately
            return await ctx.send("❌ For security, please DM me this command with your token.", delete_after=10)

        if not token:
            return await ctx.send("❌ Please provide a session token.")

        status_msg = await ctx.send("🔄 Verifying token and starting extraction... (This takes time)")

        # Run the blocking extraction function in the background executor
        loop = asyncio.get_event_loop()
        
        # This prevents the bot from freezing while downloading
        link, error = await loop.run_in_executor(
            self.executor, 
            self.run_extraction, 
            token, 
            ctx.author.id
        )

        if error:
            await status_msg.edit(content=f"❌ Error: {error}")
        else:
            await status_msg.edit(content=f"✅ Extraction Complete!\n📂 Google Drive Link: {link}")

async def setup(bot):
    await bot.add_cog(Extractor(bot))