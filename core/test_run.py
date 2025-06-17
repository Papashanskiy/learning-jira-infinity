from main import run_daily, logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting test run...")
    run_daily()
    logging.info("Test run completed")
