import pandas as pd

def list_sheets(filepath: str):
    xls = pd.ExcelFile(filepath)
    return xls.sheet_names

def load_trial(filepath: str, sheet_name=0) -> pd.DataFrame:
    df = pd.read_excel(filepath, sheet_name=sheet_name, skiprows=1)
    
    df["time_s"] = df["time"] / 1_000_000.0
    df["dt_s"] = df["time_s"].diff()
    df.loc[0, "dt_s"] = df["dt_s"].iloc[1] if len(df) > 1 else 0.01
    
    df["voltage"] = df["MotorVoltage"]
    
    df["current"] = df["Current"]
    
    df["rpm"] = df["Velocity"]

    return df[["time_s", "dt_s", "voltage", "current", "rpm", "encoderCount", "MotorStatus", "PWM"]]

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "sample.tsv"
    result = load_trial(path)
    print(result.to_string(index=False))
    print()
