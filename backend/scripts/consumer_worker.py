from app.workers.message_consumer import MessageConsumer

if __name__ == "__main__":
    consumer = MessageConsumer()
    consumer.run()
