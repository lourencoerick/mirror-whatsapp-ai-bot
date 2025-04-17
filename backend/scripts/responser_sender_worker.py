from workers.response_sender.response_sender import ResponseSender

if __name__ == "__main__":
    consumer = ResponseSender()
    consumer.run()
