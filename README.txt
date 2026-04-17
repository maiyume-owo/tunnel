pyinstaller --onefile --noconsole run.py

edit these in config.conf before use

"outbounds": [
    {
      "type": "hysteria2",
      "tag": "proxy",
      "server": "public-ip", #edit this
      "server_port": hysteria2-port,
      "password": "urpassword", #edit this
      "tls": {
        "enabled": true,
        "insecure": false,
        "server_name": "domain-name" #edit this
      },


how the script work in order.

start sing-box tunnel by running sing-box.exe -c config.conf
time sleep for tunnel to start
netsh command setting dns to 1.1.1.1
run sing-box under tray icon
