from fastapi import FastAPI,Depends,Request
from fastapi.responses import JSONResponse
import pandas as pd
import json
import utils as utils
app = FastAPI()

dataframes = {}

@app.on_event("startup")
async def load_dataframes():
    global dataframes
    dataframes["QCOM_history"] = pd.read_csv("QCOM_HISTORY.csv")
    dataframes["SBI_REFERENCE_RATES_USD"] = pd.read_csv("SBI_REFERENCE_RATES_USD.csv")
    print("Dataframes loaded!")

def get_dataframes():
    return dataframes

def get_calendar_year_dates(year):
    start_date = f'{year}-01-01'
    end_date = f'{year}-12-31'
    return start_date,end_date

def get_financial_year_dates(year):
    start_date = f'{year}-04-01'
    end_date = f'{year+1}-03-31'
    return start_date,end_date

def get_stock_purchase_price(date, hf):
    pd_date = pd.to_datetime(date)
    matched_row = hf[hf['Date'].dt.date == pd_date.date()]
    #print(pd_date.day_name())
    if matched_row.empty:
        return None

    return hf[hf['Date'].dt.date == pd_date.date()]['Close'].values[0]

def get_previous_month_last_date(date, df,date_column_name):
    date = pd.to_datetime(date)  # Convert string to datetime
    last_month = date - pd.DateOffset(months=1)
    last_month_dates = df[(df[date_column_name].dt.year == last_month.year) & (df[date_column_name].dt.month == last_month.month)]
    if not last_month_dates.empty:
        last_month_dates = last_month_dates[last_month_dates['TT BUY'] != 0]
        return last_month_dates.iloc[-1]
    else:
        return None

def get_peak_price_from_investmentdate_to_year_end(hf, start_date,year):
    calendar_start_date,calendar_end_date = get_calendar_year_dates(year)
    if start_date.date() < pd.to_datetime(calendar_start_date).date():
        start_date = pd.to_datetime(calendar_start_date)
    start_date = pd.to_datetime(start_date)
    end_date = pd.Timestamp(year=start_date.year, month=12, day=31, tz=start_date.tz)
    filtered_data = hf[(hf['Date'].dt.date >= start_date.date()) & (hf['Date'].dt.date <= end_date.date())]
    if filtered_data.empty:
        print('empty')
        return None,None
    peak_row = filtered_data.loc[filtered_data['High'].idxmax()]
    peak_date = peak_row['Date']
    peak_price = peak_row['High']
    return peak_date,peak_price

def get_calendar_year_closing_price_with_date(hf, year):
    yearly_data = hf[hf['Date'].dt.year == year]
    if yearly_data.empty:
        return None,None
    return yearly_data.iloc[-1]['Close'],yearly_data.iloc[-1]['Date']

def get_financial_year_dividends_in_usd(qt,initial_investment_date,dividends_history,year):
    financial_year_start_date, financial_year_end_date = get_financial_year_dates(year)
    fy_dividends = dividends_history[(dividends_history['Date'].dt.date >= pd.to_datetime(financial_year_start_date).date()) & (dividends_history['Date'].dt.date <= pd.to_datetime(financial_year_end_date).date())]
    initial_investment_date = pd.to_datetime(initial_investment_date)
    sliced_df = fy_dividends[(fy_dividends['Date'].dt.date > initial_investment_date.date())][['Date','SBI_TT_BUY','Dividends']]
    total_dividend = 0
    #print(sliced_df)
    for row in sliced_df.iterrows():
        #print(total_dividend)
        total_dividend += qt*row[1]['Dividends']
    return total_dividend

def get_financial_year_dividends(qt,initial_investment_date,dividends_history,year):
    financial_year_start_date, financial_year_end_date = get_financial_year_dates(year)
    fy_dividends = dividends_history[(dividends_history['Date'].dt.date >= pd.to_datetime(financial_year_start_date).date()) & (dividends_history['Date'].dt.date <= pd.to_datetime(financial_year_end_date).date())]
    initial_investment_date = pd.to_datetime(initial_investment_date)
    sliced_df = fy_dividends[(fy_dividends['Date'].dt.date > initial_investment_date.date())][['Date','SBI_TT_BUY','Dividends']]
    total_dividend = 0
    #print(sliced_df)
    for row in sliced_df.iterrows():
        #print(total_dividend)
        total_dividend += row[1]['SBI_TT_BUY']*qt*row[1]['Dividends']
    return total_dividend

class my_investment_dict:
    def __init__(self):
        self.investment_dict = []
    def add_investment(self,stock_code,investment_type,stock_quantity,stock_price,investment_date):
        self.investment_dict.append({'stock_code':stock_code,'investment_type':investment_type,
                                     'stock_quantity':stock_quantity,'stock_price':stock_price,'investment_date':investment_date})
    def get_investment_dict(self):
        return self.investment_dict
    

def prepare_iv_dict(req_json):
    iv = my_investment_dict()
    for inv in req_json:
        iv.add_investment(inv['stock_code'],inv['investment_type'],inv['stock_quantity'],inv['stock_price'],inv['investment_date'])
    return iv.get_investment_dict()


@app.get("/")
async def home(df_store: dict = Depends(get_dataframes)):
    df = df_store['QCOM_history']
    return f"Dataframe Sample {df.head().to_dict(orient='records')}"

@app.get("/check")
async def get_investment_history(request:Request):
    try:
        json_data = await request.json()
    except json.decoder.JSONDecodeError as Exception:
        json_response = {"Error":"Invalid JSON Data"}
        return JSONResponse(content=json_response,status_code=400)
    iv = prepare_iv_dict(json_data)
    iv_df = pd.DataFrame(iv)
    data = iv_df.to_dict(orient='records')
    return iv_df.to_dict(orient='records')


@app.get("/compute")
async def get_investment_history(request:Request):
    try:
        json_data = await request.json()
    except json.decoder.JSONDecodeError:
        json_response = {"Error": "Invalid JSON Data"}
        return JSONResponse(content=json_response, status_code=400)

    year = 2024
    iv = prepare_iv_dict(json_data)
    iv_df = pd.DataFrame(iv)
    iv_df['investment_date'] = pd.to_datetime(iv_df['investment_date'],utc=True)

    iv_df['investment_date'] = pd.to_datetime(iv_df['investment_date'], format='%Y-%m-%d', errors='coerce')

    hf = dataframes['QCOM_history']
    hf['Date'] = pd.to_datetime(hf['Date'], utc=True)

    df = dataframes['SBI_REFERENCE_RATES_USD']
    df['DATE'] = pd.to_datetime(df['DATE'], utc=True)

    dividends_history = hf[hf['Dividends'] != 0].copy(deep=True)
    fin_start_date, fin_end_date = get_financial_year_dates(year)
    dividends_history = dividends_history[
        (dividends_history['Date'].dt.date > pd.to_datetime(fin_start_date).date()) &
        (dividends_history['Date'].dt.date < pd.to_datetime(fin_end_date).date())
    ]
    dividends_history['SBI_TT_BUY'] = dividends_history.apply(
        lambda row: get_previous_month_last_date(row['Date'], df, 'DATE')['TT BUY'], axis=1
    )

    iv_df['stock_price'] = iv_df['stock_price'].str.replace('$', '').astype('float64')
    iv_df['stock_price_yf'] = iv_df.apply(lambda row: get_stock_purchase_price(row['investment_date'], hf), axis=1)
    iv_df['SBI_TT_BUY'] = iv_df.apply(lambda row: get_previous_month_last_date(row['investment_date'], df, 'DATE')['TT BUY'], axis=1)
    iv_df['investment_value_INR'] = iv_df['stock_price'] * iv_df['stock_quantity'] * iv_df['SBI_TT_BUY']
    iv_df['investment_value_USD'] = iv_df['stock_price'] * iv_df['stock_quantity']
    iv_df['peak_date'] = iv_df.apply(lambda row: get_peak_price_from_investmentdate_to_year_end(hf, row['investment_date'], year)[0], axis=1)
    iv_df['peak_price'] = iv_df.apply(lambda row: get_peak_price_from_investmentdate_to_year_end(hf, row['investment_date'], year)[1], axis=1)
    iv_df['SBI_TT_BUY_PEAK'] = iv_df['peak_date'].apply(lambda date: get_previous_month_last_date(date, df, 'DATE')['TT BUY'])
    iv_df['peak_value_INR'] = iv_df['peak_price'] * iv_df['stock_quantity'] * iv_df['SBI_TT_BUY_PEAK']
    iv_df['peak_value_USD'] = iv_df['peak_price'] * iv_df['stock_quantity']

    iv_df['closing_price'], iv_df['closing_date'] = zip(*iv_df['investment_date'].apply(lambda date: get_calendar_year_closing_price_with_date(hf, year)))
    iv_df['SBI_TT_BUY_CLOSING'] = iv_df['closing_date'].apply(lambda date: get_previous_month_last_date(date, df, 'DATE')['TT BUY'])
    iv_df['closing_value_INR'] = iv_df['closing_price'] * iv_df['stock_quantity'] * iv_df['SBI_TT_BUY_CLOSING']
    iv_df['closing_value_USD'] = iv_df['closing_price'] * iv_df['stock_quantity']

    iv_df['total_dividend_INR'] = iv_df.apply(lambda row: get_financial_year_dividends(row['stock_quantity'], row['investment_date'], dividends_history, year), axis=1)
    iv_df['total_dividend_USD'] = iv_df.apply(lambda row: get_financial_year_dividends_in_usd(row['stock_quantity'], row['investment_date'], dividends_history, year), axis=1)
    
    iv_df['investment_date'] = iv_df['investment_date'].dt.date.astype(str)
    iv_df['peak_date'] = iv_df['peak_date'].dt.date.astype(str)
    iv_df['closing_date'] = iv_df['closing_date'].dt.date.astype(str)

    data = iv_df.to_dict(orient='records')
    return JSONResponse(content=data,status_code=200)


