use teloxide::{prelude::*, utils::command::BotCommands};

#[derive(BotCommands, Clone)]
#[command(rename_rule = "lowercase", description = "В боте доступны следующие команды:")]
enum Commands {

    #[command(description = "Показывает список команд в боте")]
    Help,

    #[command(description = "Отображает расписание на сегодня")]
    Timetable

}


#[tokio::main]
async fn main() {
    pretty_env_logger::init();

    log::info!("Starting TKUIK-Bot...");

    let bot = Bot::from_env();
    Commands::repl(bot, answer).await;
}

async fn answer(bot: Bot, message: Message, command: Commands) -> ResponseResult<()> {
    match command {
        Commands::Help => bot.send_message(message.chat.id, Commands::descriptions().to_string()).await?,
        Commands::Timetable => bot.send_message(message.chat.id, "Здесь будет расписание юзера").await?
    };

    Ok(())
}