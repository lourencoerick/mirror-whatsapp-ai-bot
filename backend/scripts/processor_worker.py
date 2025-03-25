from app.workers.message_processor import MessageProcessor

if __name__ == "__main__":
    consumer = MessageProcessor()
    consumer.run()
