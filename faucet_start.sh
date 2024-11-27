#!/bin/bash

file_hosts='deploy_hosts.txt'

# 检查是否有传入参数
if [ -n "$1" ]; then
    # 如果有参数，将第一个参数赋值给 file_hosts
    file_hosts="$1"
fi

# 判断传入的 file_hosts 文件是否存在
if [ -f "$file_hosts" ]; then
    echo "当前处理的文件是 $file_hosts"
else
    echo "传入的参数不是文件[$file_hosts]，作为单个 host 执行"
    echo $file_hosts > faucet_hosts_temp.txt
	file_hosts='faucet_hosts_temp.txt'
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "############################################################"
echo "准备 purse address ..."
PATH_DATAS="$SCRIPT_DIR/datas"
PATH_PURSE="$PATH_DATAS/purse"
PATH_STATUS="$PATH_DATAS/status"

for i in `cat $file_hosts`; do
    echo "===========" [Step 5] $i "===========";
    FILE_PURSE="$PATH_PURSE/purse_$i.csv"
    FILE_STATUS="$PATH_STATUS/status_$i.csv"

    ssh $i "
        mkdir -p ~/faucet/datas/purse
        mkdir -p ~/faucet/datas/status
    ";

    if [ ! -f $FILE_PURSE ]; then
        echo 'Error! Purse file is not exist. Exit !'
        exit 1
    else
        echo 'FILE_PURSE: $FILE_PURSE'
        cat $FILE_PURSE
        rsync -avuzP $FILE_PURSE $i:~/faucet/datas/purse/purse.csv
    fi
    if [ ! -f $FILE_STATUS ]; then
        echo 'Error! Status file is not exist. Exit !'
        exit 1
    else
        echo 'FILE_STATUS: $FILE_STATUS'
        cat $FILE_STATUS
        rsync -avuzP $FILE_STATUS $i:~/faucet/datas/status/status.csv
    fi
done

echo "############################################################"
echo "启动 python 脚本"

for i in `cat $file_hosts`; do
    echo "===========" [Step 5] $i "===========";
    ssh $i "
        if ! screen -list | grep -qw faucet; then
            echo 'Creating new screen session for faucet...';
            screen -dmS faucet || { echo 'Failed to create screen session.'; exit 1; }
            screen -S faucet -X stuff \"cd faucet/ && python3 nillion_faucet.py --sleep_sec_min=600 --sleep_sec_max=1800 --loop_interval=60\n\" || { echo 'Failed to send commands to screen session.'; exit 1; }
        else
            echo 'Screen session faucet already exists.';
        fi;
    ";
done

# screen -d -r faucet 2>/dev/null || { echo 'Failed to attach to screen session faucet.'; exit 1; }

#             screen -S faucet -X stuff \"cd faucet/ && python3 nillion_faucet.py --profile=$i\n\" || { echo 'Failed to send commands to screen session.'; exit 1; }


echo "Finish !"
