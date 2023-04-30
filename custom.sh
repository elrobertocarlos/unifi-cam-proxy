#/bin/sh
echo starting!
echo $@

ffmpeg -hide_banner -nostdin -loglevel error -y \
-re -i "bbb_sunflower_1080p_15fps_nvenc.mp4" \
-c:v h264_nvenc -rc 2 -forced-idr 1 -cbr 1 -zerolatency 1 -tune ll -preset fast -profile main -movflags +faststart -g 30 \
-filter:v "fps=15,scale=$5,drawtext=fontfile=/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf: text='%{pts \: hms} $5 ': fontsize=24 : x=100 : y=50 : box=1" -bsf:v "h264_metadata=tick_rate=30,h264_mp4toannexb" \
-ar 32000 -ac 1 -codec:a aac -b:a 64k \
-metadata streamName=$2 -f flv - | /bin/python -m unifi.clock_sync | nc $3 $4 > $2.$5.out.bin