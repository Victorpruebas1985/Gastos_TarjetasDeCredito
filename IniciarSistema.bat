@echo off
cd /d "C:\Users\PIXART\Desktop\FISICA\VICTOR\GastosTarjetasDeCredito"
call venv\Scripts\activate
echo Iniciando sistema de Gastos...
streamlit run app.py
pause