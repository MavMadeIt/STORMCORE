import json, os
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl
from PySide6.QtGui import QColor, QFont, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QTabWidget, QFrame, QGridLayout,
    QMessageBox, QComboBox, QTextEdit, QFileDialog, QSystemTrayIcon, QMenu,
    QSplitter, QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QProgressBar
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from . import api
from .graphics import create_forecast_graphic

APP_DIR = Path.home() / ".stormcore"
APP_DIR.mkdir(exist_ok=True)
SAVED_FILE = APP_DIR / "saved_locations.json"

STYLE = """
QMainWindow,QWidget {background:#081321;color:#e7f0f8;font-family:'Segoe UI';font-size:13px}
QFrame#panel {background:#102033;border:1px solid #1d3a55;border-radius:10px}
QLabel#muted {color:#8da8bf}
QLabel#big {font-size:34px;font-weight:700;color:white}
QLabel#section {font-size:18px;font-weight:700;color:#ffffff}
QPushButton {background:#12395a;border:1px solid #24618c;border-radius:6px;padding:9px 14px;color:#eef7ff}
QPushButton:hover {background:#18517d}
QPushButton#danger {background:#642a35;border-color:#a13d4a}
QLineEdit,QComboBox,QTextEdit {background:#0b1b2b;border:1px solid #29465f;border-radius:6px;padding:9px;color:#eef7ff}
QTabWidget::pane {border:1px solid #1d3a55;border-radius:8px}
QTabBar::tab {background:#102033;padding:12px 18px;margin-right:4px;color:#9db5c9}
QTabBar::tab:selected {background:#16466b;color:white;border-bottom:3px solid #258fe0}
QListWidget,QTableWidget {background:#0b1b2b;border:1px solid #29465f;border-radius:6px;gridline-color:#1e354a}
QHeaderView::section {background:#15314a;color:#cde4f7;padding:7px;border:0}
"""

class Worker(QThread):
    done = Signal(object, object)
    def __init__(self, fn, *args):
        super().__init__(); self.fn=fn; self.args=args
    def run(self):
        try: self.done.emit(self.fn(*self.args), None)
        except Exception as e: self.done.emit(None, e)

def panel():
    f=QFrame(); f.setObjectName("panel"); return f

class StormCoreWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("STORMCORE — Professional Weather Command Center")
        self.resize(1500, 940); self.setMinimumSize(1100, 720); self.setStyleSheet(STYLE)
        self.location={"name":"Farmington, Missouri","latitude":37.7809,"longitude":-90.4218}
        self.current_alerts=[]; self.forecast_data={}; self.hourly_data={}; self.notified_alert_ids=set(); self.radar_mode="radar"
        self.workers=[]; self._radar_ready=False
        self._build_ui(); self._setup_tray(); self._load_saved()
        self.refresh_all()
        self.timer=QTimer(self); self.timer.timeout.connect(self.refresh_all); self.timer.start(5*60*1000)
        self.radar_timer=QTimer(self); self.radar_timer.timeout.connect(self.refresh_radar); self.radar_timer.start(10*60*1000)

    def _build_ui(self):
        central=QWidget(); self.setCentralWidget(central)
        outer=QVBoxLayout(central); outer.setContentsMargins(18,14,18,14); outer.setSpacing(12)
        header=QHBoxLayout()
        brand=QLabel("STORMCORE"); brand.setStyleSheet("font-size:27px;font-weight:900;color:#4cb4ff;letter-spacing:2px")
        sub=QLabel("WEATHER COMMAND CENTER"); sub.setObjectName("muted")
        header.addWidget(brand); header.addWidget(sub); header.addStretch()
        self.status=QLabel("CONNECTING TO NOAA / NWS"); self.status.setObjectName("muted")
        header.addWidget(self.status)
        outer.addLayout(header)
        searchrow=QHBoxLayout()
        self.search=QLineEdit(); self.search.setPlaceholderText("Search city or ZIP code…")
        self.search.returnPressed.connect(self.search_city)
        btn=QPushButton("SEARCH"); btn.clicked.connect(self.search_city)
        self.saved_combo=QComboBox(); self.saved_combo.setMinimumWidth(220); self.saved_combo.currentIndexChanged.connect(self.select_saved)
        save=QPushButton("☆ SAVE LOCATION"); save.clicked.connect(self.save_location)
        searchrow.addWidget(self.search,3); searchrow.addWidget(btn); searchrow.addWidget(self.saved_combo,1); searchrow.addWidget(save)
        outer.addLayout(searchrow)
        self.tabs=QTabWidget(); outer.addWidget(self.tabs,1)
        self._build_overview(); self._build_radar(); self._build_alerts(); self._build_forecasts(); self._build_stations(); self._build_studio()
        holiday_text=self._upcoming_holidays()
        self.holiday_brief.setText("UPCOMING U.S. HOLIDAYS  •  "+holiday_text)
        self.holiday_forecast.setText("UPCOMING U.S. HOLIDAYS  •  "+holiday_text)

    def _build_overview(self):
        page=QWidget(); layout=QVBoxLayout(page)
        top=QHBoxLayout()
        self.place_label=QLabel(self.location["name"]); self.place_label.setObjectName("section")
        self.temp=QLabel("—°"); self.temp.setObjectName("big")
        self.condition=QLabel("Waiting for forecast data"); self.condition.setObjectName("muted")
        top.addWidget(self.place_label); top.addStretch(); top.addWidget(self.temp); top.addWidget(self.condition)
        layout.addLayout(top)
        grid=QGridLayout()
        self.alert_summary=self._metric("ACTIVE ALERTS","—","Warnings, watches and advisories")
        self.wind_metric=self._metric("WIND","—","Current forecast wind")
        self.humidity_metric=self._metric("HUMIDITY","—","Latest observation")
        self.updated_metric=self._metric("LAST UPDATE","—","Automatic refresh every 5 min")
        for i,w in enumerate([self.alert_summary,self.wind_metric,self.humidity_metric,self.updated_metric]): grid.addWidget(w,0,i)
        layout.addLayout(grid)
        self.overview_alerts=QListWidget(); self.overview_alerts.setMaximumHeight(220)
        layout.addWidget(QLabel("LOCAL HAZARD BRIEFING")); layout.addWidget(self.overview_alerts)
        self.holiday_brief=QLabel("UPCOMING U.S. HOLIDAYS  •  Loading…"); self.holiday_brief.setObjectName("muted"); layout.addWidget(self.holiday_brief)
        self.overview_note=QLabel("Data sources: National Weather Service / NOAA and RainViewer radar.")
        self.overview_note.setObjectName("muted"); layout.addWidget(self.overview_note)
        self.tabs.addTab(page,"COMMAND OVERVIEW")

    def _metric(self,title,value,desc):
        f=panel(); l=QVBoxLayout(f)
        a=QLabel(title); a.setObjectName("muted")
        b=QLabel(value); b.setStyleSheet("font-size:25px;font-weight:700;color:white")
        c=QLabel(desc); c.setObjectName("muted")
        l.addWidget(a); l.addWidget(b); l.addWidget(c)
        f.value_label=b
        return f

    def _build_radar(self):
        page=QWidget(); l=QVBoxLayout(page)
        bar=QHBoxLayout(); title=QLabel("LIVE WEATHER MAP"); title.setObjectName("section")
        self.radar_mode_combo=QComboBox(); self.radar_mode_combo.addItem("RADAR / PRECIPITATION","radar"); self.radar_mode_combo.addItem("WIND CONDITIONS","wind"); self.radar_mode_combo.addItem("SNOW CONDITIONS","snow"); self.radar_mode_combo.addItem("HAIL ALERTS","hail")
        self.radar_mode_combo.currentIndexChanged.connect(self.change_radar_mode)
        self.radar_label=QLabel("Loading map layers…"); self.radar_label.setObjectName("muted")
        zoom_in=QPushButton("＋"); zoom_in.setMaximumWidth(42); zoom_in.clicked.connect(lambda:self.map.page().runJavaScript("zoomIn()"))
        zoom_out=QPushButton("－"); zoom_out.setMaximumWidth(42); zoom_out.clicked.connect(lambda:self.map.page().runJavaScript("zoomOut()"))
        reload_btn=QPushButton("REFRESH"); reload_btn.clicked.connect(self.refresh_radar)
        bar.addWidget(title); bar.addWidget(self.radar_mode_combo); bar.addStretch(); bar.addWidget(self.radar_label); bar.addWidget(zoom_in); bar.addWidget(zoom_out); bar.addWidget(reload_btn); l.addLayout(bar)
        self.map=QWebEngineView(); self.map.setHtml((Path(__file__).parent/"radar.html").read_text(),QUrl("https://localhost/"))
        self.map.loadFinished.connect(self._radar_loaded); l.addWidget(self.map,1)
        self.tabs.addTab(page,"LIVE RADAR")

    def _radar_loaded(self,ok):
        self._radar_ready=bool(ok)
        if ok: self.refresh_radar()

    def refresh_radar(self):
        def work():
            data=api.radar_metadata()
            frames=data.get("radar",{}).get("past",[])
            if not frames: raise ValueError("No radar frames currently available")
            frame=frames[-1]
            return data["host"], frame["path"], frame.get("time")
        self._run(work, self._radar_result)

    def _radar_result(self,result,error):
        if error:
            self.radar_label.setText("Radar feed unavailable — retrying")
            return
        host,path,timestamp=result
        tile=f"{host}{path}/256/{{z}}/{{x}}/{{y}}/2/1_1.png"
        self.radar_tile=tile
        if self._radar_ready:
            self.map.page().runJavaScript(f"setRadar({json.dumps(tile)}); setLocation({self.location['latitude']},{self.location['longitude']},6);")
            self.change_radar_mode()
        self.radar_label.setText("RainViewer precipitation radar • latest frame")

    def change_radar_mode(self,*_):
        if not self._radar_ready: return
        mode=self.radar_mode_combo.currentData()
        self.radar_mode=mode
        lat,lon=self.location["latitude"],self.location["longitude"]
        if mode=="radar":
            self.map.page().runJavaScript("setMode('radar',0,0,'');")
            self.radar_label.setText("Live precipitation radar • RainViewer")
            return
        if mode=="wind":
            periods=self.hourly_data.get("periods",[]) if self.hourly_data else []
            p=periods[0] if periods else {}
            detail=f"Forecast wind: {p.get('windSpeed','Not available')} {p.get('windDirection','')} • NWS hourly forecast"
            self.radar_label.setText("Wind forecast at selected location • NWS")
        elif mode=="snow":
            periods=self.forecast_data.get("periods",[]) if self.forecast_data else []
            text=" ".join((x.get("shortForecast","")+" "+x.get("detailedForecast","")) for x in periods[:8]).lower()
            detail="Snow appears in the available local forecast." if "snow" in text or "flurr" in text or "wintry" in text else "No snow mentioned in the current local NWS forecast."
            self.radar_label.setText("Snow forecast summary at selected location • NWS")
        else:
            hail=[x.get("properties",{}) for x in self.current_alerts if "hail" in x.get("properties",{}).get("event","").lower() or "hail" in x.get("properties",{}).get("description","").lower()]
            detail=f"{len(hail)} active NWS alert(s) mention hail at or near this location." if hail else "No active NWS alerts mentioning hail for this location. This is not a hail radar scan."
            self.radar_label.setText("Hail-related official alerts • NWS")
        self.map.page().runJavaScript(f"setMode({json.dumps(mode)},{lat},{lon},{json.dumps(detail)});")

    def _build_alerts(self):
        page=QWidget(); l=QVBoxLayout(page)
        row=QHBoxLayout(); t=QLabel("ACTIVE NWS / NOAA ALERTS"); t.setObjectName("section")
        self.alert_count=QLabel("No data"); self.alert_count.setObjectName("muted")
        refresh=QPushButton("REFRESH ALERTS"); refresh.clicked.connect(self.refresh_alerts)
        row.addWidget(t); row.addStretch(); row.addWidget(self.alert_count); row.addWidget(refresh); l.addLayout(row)
        split=QSplitter()
        self.alert_list=QListWidget(); self.alert_detail=QTextEdit(); self.alert_detail.setReadOnly(True)
        self.alert_list.currentRowChanged.connect(self.show_alert_detail)
        split.addWidget(self.alert_list); split.addWidget(self.alert_detail); split.setSizes([440,850])
        l.addWidget(split,1)
        self.tabs.addTab(page,"WARNINGS & ALERTS")

    def _build_forecasts(self):
        page=QWidget(); l=QVBoxLayout(page)
        title=QLabel("FORECAST CENTER"); title.setObjectName("section"); l.addWidget(title)
        self.forecast_table=QTableWidget(0,5); self.forecast_table.setHorizontalHeaderLabels(["PERIOD","TEMPERATURE","WIND","PRECIPITATION","FORECAST"])
        self.forecast_table.horizontalHeader().setSectionResizeMode(4,QHeaderView.Stretch)
        self.forecast_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents)
        self.holiday_forecast=QLabel("UPCOMING U.S. HOLIDAYS  •  Loading…"); self.holiday_forecast.setObjectName("muted"); l.addWidget(self.holiday_forecast)
        l.addWidget(QLabel("7-DAY FORECAST")); l.addWidget(self.forecast_table,1)
        l.addWidget(QLabel("NEWS-STYLE HOURLY WEATHER TIMELINE"))
        self.hourly_strip=QScrollArea(); self.hourly_strip.setWidgetResizable(True); self.hourly_strip.setFixedHeight(190); self.hourly_strip.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded); self.hourly_strip.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.hourly_strip_content=QWidget(); self.hourly_strip_layout=QHBoxLayout(self.hourly_strip_content); self.hourly_strip_layout.setContentsMargins(4,4,4,4); self.hourly_strip_layout.setSpacing(8); self.hourly_strip.setWidget(self.hourly_strip_content); l.addWidget(self.hourly_strip)
        self.hourly_table=QTableWidget(0,4); self.hourly_table.setHorizontalHeaderLabels(["TIME","TEMP","WIND","CONDITIONS"])
        self.hourly_table.horizontalHeader().setSectionResizeMode(3,QHeaderView.Stretch)
        l.addWidget(QLabel("HOURLY FORECAST — NEXT 24 HOURS")); l.addWidget(self.hourly_table,1)
        self.tabs.addTab(page,"FORECASTS")

    def _upcoming_holidays(self):
        from datetime import date, timedelta
        today=date.today(); found=[]
        def nth_weekday(year,month,weekday,n):
            d=date(year,month,1); return d+timedelta(days=(weekday-d.weekday())%7+7*(n-1))
        def last_weekday(year,month,weekday):
            d=date(year+ (month==12), month%12+1, 1)-timedelta(days=1)
            return d-timedelta(days=(d.weekday()-weekday)%7)
        for year in (today.year,today.year+1):
            fixed=[("New Year's Day",date(year,1,1)),("Juneteenth",date(year,6,19)),("Independence Day",date(year,7,4)),("Veterans Day",date(year,11,11)),("Christmas Day",date(year,12,25))]
            fixed += [("Martin Luther King Jr. Day",nth_weekday(year,1,0,3)),("Presidents Day",nth_weekday(year,2,0,3)),("Memorial Day",last_weekday(year,5,0)),("Labor Day",nth_weekday(year,9,0,1)),("Columbus Day",nth_weekday(year,10,0,2)),("Thanksgiving",nth_weekday(year,11,3,4))]
            for name,day in fixed:
                if day>=today: found.append((day,name))
        found.sort()
        return "   •   ".join(f"{d.strftime('%b %d')} {name}" for d,name in found[:3]) or "Holiday calendar unavailable"

    def _build_stations(self):
        page=QWidget(); l=QVBoxLayout(page)
        title=QLabel("WEATHER STATION OBSERVATIONS"); title.setObjectName("section"); l.addWidget(title)
        row=QHBoxLayout(); self.station_combo=QComboBox(); self.station_combo.setMinimumWidth(360)
        self.station_combo.currentIndexChanged.connect(self.load_station)
        self.station_info=QLabel("Choose a nearby NWS observation station."); self.station_info.setObjectName("muted")
        row.addWidget(self.station_combo); row.addWidget(self.station_info,1); l.addLayout(row)
        self.station_table=QTableWidget(0,2); self.station_table.setHorizontalHeaderLabels(["MEASUREMENT","LATEST VALUE"])
        self.station_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); l.addWidget(self.station_table,1)
        self.tabs.addTab(page,"STATION DATA")

    def _build_studio(self):
        page=QWidget(); l=QVBoxLayout(page)
        title=QLabel("WEATHER BROADCAST STUDIO"); title.setObjectName("section"); l.addWidget(title)
        l.addWidget(QLabel("Create a shareable forecast graphic using your local forecast and editorial copy."))
        self.studio_headline=QLineEdit(); self.studio_headline.setPlaceholderText("Headline — e.g. Strong storms possible this afternoon")
        self.studio_details=QTextEdit(); self.studio_details.setPlaceholderText("Write the forecast discussion, timing, impacts and preparedness message…")
        self.studio_details.setMinimumHeight(180)
        row=QHBoxLayout(); self.generate_btn=QPushButton("GENERATE BROADCAST GRAPHIC"); self.generate_btn.clicked.connect(self.generate_graphic)
        self.preview=QLabel("Graphic preview will appear here"); self.preview.setAlignment(Qt.AlignCenter); self.preview.setMinimumHeight(330); self.preview.setStyleSheet("background:#0b1b2b;border:1px dashed #31506c;border-radius:8px")
        row.addWidget(self.generate_btn); row.addStretch(); l.addLayout(row); l.addWidget(self.studio_headline); l.addWidget(self.studio_details); l.addWidget(self.preview,1)
        self.tabs.addTab(page,"BROADCAST STUDIO")

    def _run(self,fn,callback,*args):
        worker=Worker(fn,*args); self.workers.append(worker)
        worker.done.connect(lambda result,error: callback(result,error))
        worker.finished.connect(lambda: self.workers.remove(worker) if worker in self.workers else None)
        worker.start()

    def refresh_all(self):
        self.status.setText("UPDATING WEATHER DATA…")
        lat,lon=self.location["latitude"],self.location["longitude"]
        self._run(api.forecast, lambda r,e:self._forecast_result(r,e,False), lat,lon,False)
        self._run(api.forecast, lambda r,e:self._forecast_result(r,e,True), lat,lon,True)
        self.refresh_alerts()
        self._run(api.stations, self._stations_result, lat,lon)

    def _forecast_result(self,result,error,hourly):
        if error:
            self.status.setText("NWS DATA CONNECTION ISSUE")
            return
        if hourly:
            self.hourly_data=result
            self._populate_hourly(result)
        else:
            self.forecast_data=result
            self._populate_forecast(result)
            periods=result.get("periods",[])
            if periods:
                self.temp.setText(f'{periods[0].get("temperature","—")}°{periods[0].get("temperatureUnit","F")}')
                self.condition.setText(periods[0].get("shortForecast",""))
                self.wind_metric.value_label.setText(periods[0].get("windSpeed","—"))
            self.updated_metric.value_label.setText(datetime.now().strftime("%I:%M %p"))
            self.status.setText("LIVE NWS DATA • AUTO-REFRESH ON")

    def _populate_forecast(self,data):
        periods=data.get("periods",[])
        self.forecast_table.setRowCount(min(len(periods),14))
        for i,p in enumerate(periods[:14]):
            vals=[p.get("name",""),f'{p.get("temperature","—")}°{p.get("temperatureUnit","")}',f'{p.get("windSpeed","—")} {p.get("windDirection","")}',f'{(p.get("probabilityOfPrecipitation") or {}).get("value","—")}%',p.get("detailedForecast",p.get("shortForecast",""))]
            for j,v in enumerate(vals): self.forecast_table.setItem(i,j,QTableWidgetItem(str(v)))

    def _populate_hourly(self,data):
        periods=data.get("periods",[])[:24]; self.hourly_table.setRowCount(len(periods))
        while self.hourly_strip_layout.count():
            item=self.hourly_strip_layout.takeAt(0); widget=item.widget()
            if widget: widget.deleteLater()
        for i,p in enumerate(periods):
            vals=[api.parse_time(p.get("startTime")),f'{p.get("temperature","—")}°{p.get("temperatureUnit","")}',f'{p.get("windSpeed","—")} {p.get("windDirection","")}',p.get("shortForecast","")]
            for j,v in enumerate(vals): self.hourly_table.setItem(i,j,QTableWidgetItem(str(v)))
            card=QFrame(); card.setObjectName("panel"); card.setFixedWidth(150); cl=QVBoxLayout(card)
            tm=QLabel(vals[0]); tm.setObjectName("muted"); cl.addWidget(tm)
            temp=QLabel(vals[1]); temp.setStyleSheet("font-size:23px;font-weight:800;color:white"); cl.addWidget(temp)
            cond=QLabel(vals[3]); cond.setWordWrap(True); cond.setMinimumHeight(38); cl.addWidget(cond)
            chance=(p.get("probabilityOfPrecipitation") or {}).get("value")
            cl.addWidget(QLabel(f"RAIN  {chance if chance is not None else '—'}%"))
            bar=QProgressBar(); bar.setRange(0,100); bar.setValue(max(0,min(100,int(chance or 0)))); bar.setTextVisible(False); bar.setFixedHeight(9); cl.addWidget(bar)
            wind=QLabel(f"WIND  {vals[2]}"); wind.setObjectName("muted"); cl.addWidget(wind)
            self.hourly_strip_layout.addWidget(card)
        self.hourly_strip_layout.addStretch(1)

    def refresh_alerts(self):
        self._run(api.alerts,self._alerts_result,self.location["latitude"],self.location["longitude"])

    def _alerts_result(self,result,error):
        if error:
            self.alert_count.setText("Alert feed unavailable")
            return
        self.current_alerts=result
        self.alert_list.clear(); self.overview_alerts.clear()
        new_alerts=[]
        for feature in result:
            p=feature.get("properties",{})
            event=p.get("event","Weather alert")
            alert_id=feature.get("id") or p.get("id") or f"{event}:{p.get('sent', '')}:{p.get('areaDesc', '')}"
            if alert_id not in self.notified_alert_ids:
                new_alerts.append(event)
                self.notified_alert_ids.add(alert_id)
            severity=p.get("severity","Unknown")
            headline=p.get("headline") or p.get("description","")
            item=QListWidgetItem(f"{event}  •  {severity}")
            item.setData(Qt.UserRole,feature)
            if "Tornado Warning" in event or "Flash Flood Warning" in event:
                item.setForeground(QColor("#ff656b"))
            self.alert_list.addItem(item)
            self.overview_alerts.addItem(f"●  {event} — {p.get('areaDesc','')}")
        if new_alerts and hasattr(self, "tray") and self.tray.isVisible():
            self.tray.showMessage("STORMCORE • New NWS alert", ", ".join(new_alerts[:3]), QSystemTrayIcon.Warning, 10000)
        self.alert_count.setText(f"{len(result)} active alert(s)")
        self.alert_summary.value_label.setText(str(len(result)))
        if not result: self.overview_alerts.addItem("No active NWS alerts for this location.")
        self.status.setText("LIVE NWS DATA • AUTO-REFRESH ON")
        if self.radar_mode=="hail": self.change_radar_mode()

    def show_alert_detail(self,row):
        if row<0 or row>=len(self.current_alerts): return
        p=self.current_alerts[row].get("properties",{})
        content=[
            p.get("headline",""),"",
            f"EVENT: {p.get('event','—')}",
            f"SEVERITY: {p.get('severity','—')}    CERTAINTY: {p.get('certainty','—')}",
            f"URGENCY: {p.get('urgency','—')}",
            f"AREAS: {p.get('areaDesc','—')}",
            f"ONSET: {api.parse_time(p.get('onset'))}",
            f"EXPIRES: {api.parse_time(p.get('expires'))}","",
            "DESCRIPTION",p.get("description",""),
            "INSTRUCTIONS",p.get("instruction") or "Follow official NWS and local emergency-management guidance."
        ]
        self.alert_detail.setPlainText("\n".join(content))

    def _stations_result(self,result,error):
        self.station_combo.clear()
        if error: self.station_info.setText("Station list unavailable"); return
        self.station_features=result
        for f in result[:30]:
            p=f.get("properties",{})
            self.station_combo.addItem(f'{p.get("name","Station")} ({p.get("stationIdentifier","")})',p.get("stationIdentifier"))
        self.station_info.setText(f"{min(len(result),30)} nearby stations returned by NWS")

    def load_station(self,index):
        if index<0: return
        station=self.station_combo.currentData()
        if station: self._run(api.observations,self._station_result,station)

    def _station_result(self,data,error):
        self.station_table.setRowCount(0)
        if error: self.station_info.setText("Observation unavailable"); return
        props=[
            ("Observation time",api.parse_time(data.get("timestamp"))),
            ("Temperature",self._measurement(data.get("temperature"),"°C")),
            ("Dew point",self._measurement(data.get("dewpoint"),"°C")),
            ("Relative humidity",self._measurement(data.get("relativeHumidity"),"%")),
            ("Wind speed",self._measurement(data.get("windSpeed"),"km/h")),
            ("Wind direction",self._measurement(data.get("windDirection"),"°")),
            ("Wind gust",self._measurement(data.get("windGust"),"km/h")),
            ("Pressure",self._measurement(data.get("barometricPressure"),"Pa")),
            ("Visibility",self._measurement(data.get("visibility"),"m")),
            ("Text description",data.get("textDescription") or "—")
        ]
        for name,value in props:
            r=self.station_table.rowCount(); self.station_table.insertRow(r)
            self.station_table.setItem(r,0,QTableWidgetItem(name)); self.station_table.setItem(r,1,QTableWidgetItem(str(value)))
        self.station_info.setText("Latest observation reported by the selected NWS station")

    def _measurement(self,obj,unit):
        if not isinstance(obj,dict) or obj.get("value") is None: return "—"
        val=obj["value"]
        if unit=="°C": return f"{round(val,1)} °C / {round(val*9/5+32)} °F"
        return f"{round(val,1)} {unit}"

    def search_city(self):
        query=self.search.text().strip()
        if not query: return
        self.status.setText("SEARCHING LOCATIONS…")
        self._run(api.geocode_city,self._search_result,query)

    def _search_result(self,result,error):
        if error:
            QMessageBox.warning(self,"Location search failed",str(error)); return
        if not result:
            QMessageBox.information(self,"No results","No matching city found."); return
        # Offer matches in a compact chooser.
        from PySide6.QtWidgets import QInputDialog
        labels=[x["name"] for x in result]
        chosen,ok=QInputDialog.getItem(self,"Choose location","Search results:",labels,0,False)
        if ok:
            self.location=next(x for x in result if x["name"]==chosen)
            self._location_changed()

    def _location_changed(self):
        self.place_label.setText(self.location["name"])
        if self._radar_ready:
            self.map.page().runJavaScript(f"setLocation({self.location['latitude']},{self.location['longitude']},7);")
            self.change_radar_mode()
        self.refresh_all()

    def _load_saved(self):
        try: self.saved_locations=json.loads(SAVED_FILE.read_text())
        except Exception: self.saved_locations=[]
        self._update_saved_combo()

    def _update_saved_combo(self):
        self.saved_combo.blockSignals(True); self.saved_combo.clear()
        self.saved_combo.addItem("Saved locations…",None)
        for x in self.saved_locations: self.saved_combo.addItem(x["name"],x)
        self.saved_combo.blockSignals(False)

    def save_location(self):
        if not any(x["name"]==self.location["name"] for x in self.saved_locations):
            self.saved_locations.append(self.location.copy())
            SAVED_FILE.write_text(json.dumps(self.saved_locations,indent=2))
            self._update_saved_combo()
            self.saved_combo.setCurrentIndex(self.saved_combo.count()-1)

    def select_saved(self,index):
        data=self.saved_combo.itemData(index)
        if data:
            self.location=data; self._location_changed()

    def generate_graphic(self):
        headline=self.studio_headline.text().strip() or "Your local forecast"
        details=self.studio_details.toPlainText().strip()
        if not details:
            periods=self.forecast_data.get("periods",[])
            details=periods[0].get("detailedForecast","Add your own forecast discussion in the text field.") if periods else "Forecast details are not available yet."
        path,ok=QFileDialog.getSaveFileName(self,"Save broadcast graphic","STORMCORE-forecast.png","PNG Image (*.png)")
        if not path: return
        try:
            create_forecast_graphic(self.location["name"],headline,details,path)
            pix=QPixmap(path)
            self.preview.setPixmap(pix.scaled(self.preview.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
            QMessageBox.information(self,"Graphic created",f"Saved forecast graphic to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self,"Graphic error",str(e))

    def _setup_tray(self):
        self.tray=QSystemTrayIcon(self)
        self.tray.setToolTip("STORMCORE Weather")
        menu=QMenu(); menu.addAction("Open STORMCORE",self.showNormal); menu.addAction("Refresh now",self.refresh_all); menu.addAction("Quit",self.close)
        self.tray.setContextMenu(menu); self.tray.show()

    def closeEvent(self,event):
        if hasattr(self,"tray"): self.tray.hide()
        event.accept()
