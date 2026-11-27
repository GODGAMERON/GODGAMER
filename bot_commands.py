from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

router = Router()


@router.message(CommandStart())
async def start_command(message: Message):
    await message.answer(
        "👋 <b>Telegram SMM Automation Bot</b>\n\n"
        "Bot active hai. Authorized commands ke liye /help bhejein.",
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "<b>BOT COMMANDS</b>\n\n"
        "Channels: /addchannel /addprivatechannel /channels /channelinfo\n"
        "Automation: /startqty /stopqty\n"
        "Services: /SERVICEID /setserviceqty /serviceinfo /Allservicenumber\n"
        "Panels: /addpanel /panels /panelinfo /checkbalance\n"
        "Orders: /orders /pendingorders /orderinfo /checkorder\n"
        "Reports: /report24 /report72 /reportday /reportweek /reportmonth\n"
        "Account: /myid\n\n"
        "Commands access permissions ke hisaab se restricted hain.",
        parse_mode="HTML"
    )
