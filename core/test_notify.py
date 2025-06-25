from main import notify_critical_error, logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting test run...")
    notify_critical_error('Test message')
    logging.info("Test run completed")
