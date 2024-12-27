import yfinance as yf
import pandas as pd
import argparse

def download_stock_data(ticker, start_date=None):
    # Download stock data
    yf_ticker = yf.Ticker(ticker)
    if start_date:
        stock_data = yf_ticker.history(start=start_date)
    else:
        stock_data = yf_ticker.history(period="max")
    
    # Save to CSV
    csv_filename = f"{ticker}_HISTORY.csv"
    stock_data.to_csv(csv_filename)
    print(f"Data for {ticker} saved to {csv_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download stock data and save to CSV.")
    parser.add_argument("--ticker", type=str, required=True, help="The stock ticker symbol")
    parser.add_argument("--start_date", type=str, help="The start date for the stock data in YYYY-MM-DD format")
    args = parser.parse_args()
    download_stock_data(args.ticker, args.start_date)