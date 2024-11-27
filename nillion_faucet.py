import os # noqa
import sys # noqa
import argparse
import random
import time
import copy
import re
from datetime import datetime, timedelta

from DrissionPage import ChromiumOptions
from DrissionPage import ChromiumPage
from DrissionPage._elements.none_element import NoneElement

from fun_utils import ding_msg
from fun_utils import get_date
from fun_utils import load_file
from fun_utils import save2file
from fun_utils import conv_time
from fun_utils import time_difference

from conf import DEF_LOCAL_PORT
from conf import MAX_PROFILE
from conf import DEF_USE_HEADLESS
from conf import DEF_DEBUG
from conf import DEF_PATH_USER_DATA
from conf import DEF_DING_TOKEN
from conf import DEF_PATH_BROWSER
from conf import DEF_PATH_DATA_STATUS
from conf import DEF_HEADER_STATUS

from conf import DEF_CAPTCHA_EXTENSION_PATH
from conf import DEF_CAPTCHA_KEY
from conf import EXTENSION_ID_YESCAPTCHA

from conf import DEF_PATH_DATA_PURSE
from conf import DEF_HEADER_PURSE

from conf import logger

"""
2024.11.26
testnet-address and server-address
record their respective claim times separately

2024.11.04
nillion faucet claim
"""


class NillionTask():
    def __init__(self) -> None:
        self.file_status = f'{DEF_PATH_DATA_STATUS}/status.csv'
        self.args = None
        self.page = None
        self.s_today = get_date(is_utc=True)

        self.n_points_spin = -1
        self.n_points = -1
        self.n_referrals = -1
        self.n_completed = -1

        # 是否有更新
        self.is_update = False

        # 账号执行情况
        self.dic_status = {}

        self.dic_purse = {}

        self.purse_load()

    def set_args(self, args):
        self.args = args
        self.is_update = False

        self.n_points_spin = -1
        self.n_points = -1
        self.n_referrals = -1
        self.n_completed = -1

    def __del__(self):
        self.status_save()
        # logger.info(f'Exit {self.args.s_profile}')

    def purse_load(self):
        self.file_purse = f'{DEF_PATH_DATA_PURSE}/purse.csv'
        self.dic_purse = load_file(
            file_in=self.file_purse,
            idx_key=0,
            header=DEF_HEADER_PURSE
        )

    def status_load(self):
        self.dic_status = load_file(
            file_in=self.file_status,
            idx_key=0,
            header=DEF_HEADER_STATUS
        )

    def status_save(self):
        save2file(
            file_ot=self.file_status,
            dic_status=self.dic_status,
            idx_key=0,
            header=DEF_HEADER_STATUS
        )

    def close(self):
        # 在有头浏览器模式 Debug 时，不退出浏览器，用于调试
        if DEF_USE_HEADLESS is False and DEF_DEBUG:
            pass
        else:
            self.page.quit()

    def get_new_profile(self, s_in):
        # 使用正则表达式提取整数部分
        match = re.search(r'\d+', s_in)

        if match:
            # 提取整数部分并计算取余
            num_str = match.group(0)
            num = int(num_str)
            new_num = num % MAX_PROFILE

            # 调整范围到 1-20
            # new_num = MAX_PROFILE if new_num == 0 else new_num
            new_num = (num - 1) % MAX_PROFILE + 1

            # 保持整数部分的长度不变
            new_num_str = f'{new_num:0{len(num_str)}d}'

            # 替换原有的数字部分并返回新的字符串
            s_out = s_in[:match.start()] + new_num_str + s_in[match.end():]
        else:
            # 如果没有找到数字部分，直接返回原字符串
            s_out = s_in

        return s_out

    def initChrome(self, s_profile):
        """
        s_profile: 浏览器数据用户目录名称
        """
        profile_path = s_profile

        co = ChromiumOptions()

        # 设置本地启动端口
        co.set_local_port(port=DEF_LOCAL_PORT)
        if len(DEF_PATH_BROWSER) > 0:
            co.set_paths(browser_path=DEF_PATH_BROWSER)
        # co.set_paths(browser_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome') # noqa

        # 阻止“自动保存密码”的提示气泡
        co.set_pref('credentials_enable_service', False)

        # 阻止“要恢复页面吗？Chrome未正确关闭”的提示气泡
        co.set_argument('--hide-crash-restore-bubble')

        # 关闭沙箱模式, 解决`$DISPLAY`报错
        # co.set_argument('--no-sandbox')

        # 设置Chrome在启动时自动打开开发者工具
        co.set_argument('--auto-open-devtools-for-tabs')

        co.set_user_data_path(path=DEF_PATH_USER_DATA)
        # co.set_user(user=profile_path)
        s_new_profile_path = self.get_new_profile(profile_path)
        if s_new_profile_path != profile_path:
            logger.info(f's_new_profile_path={s_new_profile_path}')

        co.set_user(user=s_new_profile_path)

        # 获取当前工作目录
        current_directory = os.getcwd()

        # 检查目录是否存在
        if os.path.exists(os.path.join(current_directory, DEF_CAPTCHA_EXTENSION_PATH)):
            logger.info(f'YesCaptcha plugin path: {DEF_CAPTCHA_EXTENSION_PATH}')
            co.add_extension(DEF_CAPTCHA_EXTENSION_PATH)
        else:
            print("YesCaptcha plugin directory is not exist. Exit!")
            sys.exit(1)

        # https://drissionpage.cn/ChromiumPage/browser_opt
        co.headless(DEF_USE_HEADLESS)
        co.set_user_agent(user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36') # noqa

        try:
            self.page = ChromiumPage(co)
        except Exception as e:
            logger.info(f'Error: {e}')
        finally:
            pass

        # 初始化 YesCaptcha
        self.init_yescaptcha()

    def save_screenshot(self, name):
        # 对整页截图并保存
        self.page.set.window.max()
        s_name = f'{self.args.s_profile}_{name}'
        self.page.get_screenshot(path='tmp_img', name=s_name, full_page=True)

    def init_yescaptcha(self):
        """
        chrome-extension://jiofmdifioeejeilfkpegipdjiopiekl/popup/index.html
        """
        # EXTENSION_ID = 'jiofmdifioeejeilfkpegipdjiopiekl'
        s_url = f'chrome-extension://{EXTENSION_ID_YESCAPTCHA}/popup/index.html'
        self.page.get(s_url)
        # self.page.wait.load_start()
        self.page.wait(3)

        self.save_screenshot(name='yescaptcha_1.jpg')

        x_path = 'x://*[@id="app"]/div/div[2]/div[2]/div/div[2]/div[2]/div/input'
        ele_input = self.page.ele(f'{x_path}', timeout=2)
        if not isinstance(ele_input, NoneElement):
            if ele_input.value == DEF_CAPTCHA_KEY:
                logger.info('yescaptcha key is configured')
            else:
                logger.info('input yescaptcha key ...')
                # ele_input.input(DEF_CAPTCHA_KEY, clear=True, by_js=True)
                # ele_input.click()
                tab = self.page.latest_tab
                ele_input.clear(by_js=True)
                ele_input.input(DEF_CAPTCHA_KEY, clear=True, by_js=False)
                # tab.actions.move_to(ele_input).click().type(DEF_CAPTCHA_KEY)
                ele_input.clear(by_js=True)
                ele_input.input(DEF_CAPTCHA_KEY, clear=True, by_js=False)
                # tab.actions.move_to(ele_input).click().type(DEF_CAPTCHA_KEY)
                # btn_save = self.page.ele('x://*[@id=":r6:"]', timeout=2)

                is_success = False
                for s_text in ['保存', 'save']:
                    # btn_save = self.page.ele(s_text, timeout=2)
                    btn_save = self.page.ele(f'tag:button@@text():{s_text}', timeout=2)
                    if not isinstance(btn_save, NoneElement):
                        # btn_save.click(by_js=True)
                        tab.actions.move_to(btn_save).click()
                        is_success = True
                        break
                if is_success:
                    logger.info('密钥保存成功')
                else:
                    logger.info('密钥保存失败')

            # 次数限制
            x_path = 'x://*[@id="app"]/div/div[2]/div[2]/div/div[5]/div[2]/div/input'
            ele_input = self.page.ele(x_path, timeout=2)
            if not isinstance(ele_input, NoneElement):
                s_val = '3'
                tab = self.page.latest_tab
                if ele_input.value != s_val:
                    ele_input.clear(by_js=True)
                    ele_input.input(vals=s_val, clear=True, by_js=False)
                    ele_input.clear(by_js=True)
                    ele_input.input(vals=s_val, clear=True, by_js=False)

                    is_success = False
                    for s_text in ['保存', 'save']:
                        # btn_save = self.page.ele(s_text, timeout=2)
                        btn_save = self.page.ele(f'tag:button@@text():{s_text}', timeout=2)
                        if not isinstance(btn_save, NoneElement):
                            # btn_save.click(by_js=True)
                            tab.actions.move_to(btn_save).click()
                            is_success = True
                            break
                    if is_success:
                        logger.info('次数限制保存成功')
                    else:
                        logger.info('次数限制保存失败')

                    # btn_save = self.page.ele('x://*[@id=":r7:"]', timeout=2)
                    # btn_save = self.page.ele('保存', timeout=2)
                    # if not isinstance(btn_save, NoneElement):
                    #     btn_save.click()
                    #     logger.info('次数限制保存成功')
                    # else:
                    #     logger.info('次数限制保存失败')

            # 自动开启
            x_path = 'x://*[@id="app"]/div/div[2]/div[2]/div/div[6]/div[2]/span/input'
            checkbox = self.page.ele(x_path, timeout=2)
            if not isinstance(checkbox, NoneElement):
                if checkbox.states.is_checked:
                    checkbox.click()

        logger.info('yescaptcha init success')
        self.save_screenshot(name='yescaptcha_2.jpg')

    def update_status(self, avail_claim_ts, idx_status):
        """
        idx_status:
            1 claim_time_1
            2 claim_time_2
        """
        claim_time = conv_time(avail_claim_ts, 2)
        if self.args.s_profile not in self.dic_status:
            self.dic_status[self.args.s_profile] = [
                self.args.s_profile,
                '',
                ''
            ]
        self.dic_status[self.args.s_profile][idx_status] = claim_time

    def faucet_claim(self, s_purse, idx_status):
        """
        登录及校验是否登录成功
        """
        self.page.get('https://faucet.testnet.nillion.com/')
        self.page.refresh()
        self.page.wait.load_start()

        max_try = 5
        for i in range(1, max_try):
            logger.info(f'Nillion Claim try_i={i}/{max_try}')

            # Step One
            s_path = '@@class:v-btn__content@@text():Start'
            self.page.wait.eles_loaded(f'{s_path}')

            self.save_screenshot(name='s1_001.jpg')

            button = self.page.ele(f'{s_path}', timeout=2)
            if isinstance(button, NoneElement):
                logger.info('Step One: Not Found ...')
                continue
            else:
                logger.info('Step One: Click ...')
                self.page.actions.move_to(f'{s_path}')
                button.click(by_js=True)
                self.page.wait(2)

                ele_input = self.page.ele('@id=input-34', timeout=2)
                if not isinstance(ele_input, NoneElement):
                    logger.info('Enter a wallet address ...')
                    logger.info(f'wallet address is {s_purse}')
                    ele_input.input(s_purse)
                    self.page.wait(2)

                    # CONTINUE
                    s_path = '@@class:v-btn__content@@text():Continue'
                    button = self.page.ele(f'{s_path}', timeout=2)
                    if isinstance(button, NoneElement):
                        logger.info('Step Two: Not Found ...')
                    else:
                        logger.info('Step Two: Continue ...')
                        button.click(by_js=True)
                        self.page.wait(2)
                    self.save_screenshot(name='s2_001.jpg')

            # Verification Challenge 点击识别验证码
            button = self.page.ele('tag:iframe').ele('.recaptcha-checkbox-border', timeout=2) # noqa
            if isinstance(button, NoneElement):
                logger.info('Step Three: Verification Challenge Not Found ...')
                continue
            else:
                logger.info('Step Three: Verification Challenge ...')
                button.click(by_js=True)
                self.page.wait(1)
            self.save_screenshot(name='s3_001.jpg')

            # ele_checkbox = self.page.ele('tag:iframe').ele('.recaptcha-checkbox-checkmark', timeout=2) # noqa
            # print(ele_checkbox.states.is_checked)

            # 验证已经过期，请重新选中该复选框，以便获取新的验证码

            # Recaptcha 要求验证.
            # Recaptcha requires verification.

            # 您已通过验证
            # You are verified

            max_wait_sec = 120
            i = 1
            while i < max_wait_sec:
                s_info = self.page.ele('tag:iframe').ele('.rc-anchor-aria-status', timeout=2).text # noqa
                print(f'{i}/{max_wait_sec} {s_info}')
                if s_info.startswith('You are verified') or s_info.startswith('您已通过验证'): # noqa
                    logger.info(f'Recaptcha took {i} seconds. {s_info}')
                    break
                i += 1
                self.page.wait(1)
            # 未通过验证
            if i >= max_wait_sec:
                logger.info(f'Recaptcha failed, took {i} seconds.')
                continue

            self.save_screenshot(name='s4_001.jpg')

            # CONTINUE
            s_path = '@@class:v-btn__content@@text():Continue'
            button = self.page.eles(f'{s_path}', timeout=2)
            if isinstance(button, NoneElement):
                logger.info('Continue Button is Not Found ...')
                continue
            else:
                logger.info('Click Continue Button ...')
                button[-1].click(by_js=True)
                self.page.wait(1)

            # This faucet is experiencing high load. If you run into problems funding your wallet, please try \t\t\t\tagain in a few hours.
            # s_info = self.page.ele('.font-weight-bold').text
            # print(s_info)

            i = 1
            while i < max_wait_sec:
                s_info = self.page.ele('.v-alert__content').text
                s_info = s_info.replace('\t', '')
                print(f'Took {i}/{max_wait_sec} seconds. {s_info}')
                logger.info(f'Took {i} seconds. {s_info}')
                # Done! Your requested tokens should have arrived at your provided address. You can return here in 24 \t\t\thours to request more.
                if s_info.startswith('Done! Your requested tokens should have arrived'): # noqa
                    logger.info(f'Success to claim, submit took {i} seconds.')

                    self.save_screenshot(name=f'purse_claim_{idx_status}.jpg')

                    self.update_status(time.time(), idx_status)
                    self.is_update = True
                    self.page.wait(3)
                    return True
                i += 1
                self.page.wait(1)
            # Claim Failed
            if i >= max_wait_sec:
                logger.info(f'Failed to claim, submit took {i} seconds.')
                continue

        return False


def send_msg(instNillionTask, lst_success):
    if len(DEF_DING_TOKEN) > 0 and len(lst_success) > 0:
        s_info = ''
        for s_profile in lst_success:
            if s_profile in instNillionTask.dic_status:
                lst_status = instNillionTask.dic_status[s_profile]
            else:
                lst_status = [s_profile, -1]

            s_info += '- {} {}\n'.format(
                s_profile,
                lst_status[1],
            )
        d_cont = {
            'title': 'Nillion Faucet Claim Finished',
            'text': (
                '- {}\n'
                '{}\n'
                .format(DEF_HEADER_STATUS, s_info)
            )
        }
        ding_msg(d_cont, DEF_DING_TOKEN, msgtype="markdown")


def main(args):
    if args.sleep_sec_at_start > 0:
        logger.info(f'Sleep {args.sleep_sec_at_start} seconds at start !!!') # noqa
        time.sleep(args.sleep_sec_at_start)

    instNillionTask = NillionTask()

    if len(args.profile) > 0:
        items = args.profile.split(',')
    else:
        # 从配置文件里获取钱包名称列表
        instNillionTask.purse_load()
        items = list(instNillionTask.dic_purse.keys())

    profiles = copy.deepcopy(items)

    # 每次随机取一个出来，并从原列表中删除，直到原列表为空
    total = len(profiles)
    n = 0

    lst_success = []

    while profiles:
        n += 1
        logger.info('#'*40)
        s_profile = random.choice(profiles)
        logger.info(f'progress:{n}/{total} [{s_profile}]') # noqa
        profiles.remove(s_profile)

        args.s_profile = s_profile

        def _run(idx):
            instNillionTask.initChrome(args.s_profile)

            s_purse = instNillionTask.dic_purse[instNillionTask.args.s_profile][idx] # noqa
            is_claim = instNillionTask.faucet_claim(s_purse, idx)
            instNillionTask.status_save()

            instNillionTask.close()
            return is_claim

        # 出现异常(与页面的连接已断开)，增加重试
        max_try_except = 5
        for j in range(1, max_try_except+1):
            try:
                is_claim = False
                if j > 1:
                    logger.info(f'异常重试，当前是第 {j}/{max_try_except} 次执行 [{s_profile}]') # noqa

                instNillionTask.set_args(args)
                instNillionTask.status_load()

                if s_profile in instNillionTask.dic_status:
                    lst_status = instNillionTask.dic_status[s_profile]
                else:
                    lst_status = None

                is_claim = False
                for i in [1, 2]:
                    is_ready_claim = True
                    if lst_status:
                        avail_time = lst_status[i]
                        if avail_time:
                            n_sec_wait = time_difference(avail_time) + 24*3600 + 60
                            if n_sec_wait > 0:
                                logger.info(f'[{s_profile}] [address {i}] 还需等待{n_sec_wait}秒') # noqa
                                is_ready_claim = False
                    if is_ready_claim:
                        is_claim = is_claim | _run(i)

                if is_claim:
                    lst_success.append(s_profile)
                break
            except Exception as e:
                logger.info(f'[{s_profile}] An error occurred: {str(e)}')
                if j < max_try_except:
                    time.sleep(5)

        if instNillionTask.is_update is False:
            continue

        logger.info(f'[{s_profile}] Finish')

        if len(profiles) > 0:
            sleep_time = random.randint(args.sleep_sec_min, args.sleep_sec_max)
            if sleep_time > 60:
                logger.info('sleep {} minutes ...'.format(int(sleep_time/60)))
            else:
                logger.info('sleep {} seconds ...'.format(int(sleep_time)))
            time.sleep(sleep_time)

    send_msg(instNillionTask, lst_success)


if __name__ == '__main__':
    """
    从钱包列表配置文件中，每次随机取一个出来，并从原列表中删除，直到原列表为空
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--loop_interval', required=False, default=60, type=int,
        help='[默认为 60] 执行完一轮 sleep 的时长(单位是秒)，如果是0，则不循环，只执行一次'
    )
    parser.add_argument(
        '--sleep_sec_min', required=False, default=3, type=int,
        help='[默认为 3] 每个账号执行完 sleep 的最小时长(单位是秒)'
    )
    parser.add_argument(
        '--sleep_sec_max', required=False, default=10, type=int,
        help='[默认为 10] 每个账号执行完 sleep 的最大时长(单位是秒)'
    )
    parser.add_argument(
        '--sleep_sec_at_start', required=False, default=0, type=int,
        help='[默认为 0] 在启动后先 sleep 的时长(单位是秒)'
    )
    parser.add_argument(
        '--profile', required=False, default='',
        help='按指定的 profile 执行，多个用英文逗号分隔'
    )
    args = parser.parse_args()
    if args.loop_interval <= 0:
        main(args)
    else:
        while True:
            main(args)
            logger.info('#####***** Loop sleep {} seconds ...'.format(args.loop_interval)) # noqa
            time.sleep(args.loop_interval)


"""
# noqa
python nillion_faucet.py --profile=p001
python nillion_faucet.py --profile=p010,p011 --sleep_sec_min=600 --sleep_sec_max=1800
"""
