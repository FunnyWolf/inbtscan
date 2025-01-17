# -*- coding:utf-8 -*-
import socket
import sys
from datetime import datetime
import threading
import time

lock = threading.Lock()


# from https://docs.microsoft.com/en-us/previous-versions/windows/it-pro/windows-2000-server/cc940063(v%3dtechnet.10)
UNIQUE_NAMES = {
    b'\x00': 'Workstation Service',
    b'\x03': 'Messenger Service',
    b'\x06': 'RAS Server Service',
    b'\x1F': 'NetDDE Service',
    b'\x20': 'Server Service',
    b'\x21': 'RAS Client Service',
    b'\xBE': 'Network Monitor Agent',
    b'\xBF': 'Network Monitor Application',
    b'\x03': 'Messenger Service',
    b'\x1D': 'Master Browser',
    b'\x1B': 'Domain Master Browser',
}
GROUP_NAMES = {
    b'\x00': 'Domain Name',
    b'\x1C': 'Domain Controllers',
    b'\x1E': 'Browser Service Elections',
    # Master Browser
}


NetBIOS_ITEM_TYPE = {
    b'\x01\x00':'NetBIOS computer name',
    b'\x02\x00':'NetBIOS domain name',
    b'\x03\x00':'DNS computer name',
    b'\x04\x00':'DNS domain name',
    b'\x05\x00':'DNS tree name',
    # b'\x06\x00':'',
    b'\x07\x00':'Time stamp',
}


def to_ips(raw):
    if '/' in raw:
        addr, mask = raw.split('/')
        mask = int(mask)

        bin_addr = ''.join([ (8 - len(bin(int(i))[2:])) * '0' + bin(int(i))[2:] for i in  addr.split('.')])
        start = bin_addr[:mask] + (32 - mask) * '0'
        end = bin_addr[:mask] + (32 - mask) * '1'
        bin_addrs = [ (32 - len(bin(int(i))[2:])) * '0' + bin(i)[2:] for i in range(int(start, 2), int(end, 2) + 1)]

        dec_addrs = ['.'.join([str(int(bin_addr[8*i:8*(i+1)], 2)) for i in range(0, 4)]) for bin_addr in bin_addrs]                
        # print(dec_addrs)
        return dec_addrs
    elif '-' in raw:
        addr, end = raw.split('-')
        end = int(end)
        start = int(addr.split('.')[3])
        prefix = '.'.join(addr.split('.')[:-1])
        addrs = [ prefix + '.' + str(i) for i in range(start, end + 1) ]
        # print(addrs)
        return addrs
    else:
        return [raw]


def nbns_name(addr):
    msg = ''
    data = b'ff\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00 CKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\x00\x00!\x00\x01'
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.sendto(data, (addr, 137))
        rep = s.recv(2000)
        if isinstance(rep, str):
            rep = bytes(rep)

        num = ord(rep[56:57].decode()) #  num of the answer
        data = rep[57:]  # start of the answer

        group, unique = '', ''
        # print('--------------------------')
        msg += '--------------------------' + '\n'
        for i in range(num):
            name = data[18 * i:18 *i + 15].decode()
            flag_bit = bytes(data[18 * i + 15:18 *i + 16])
            # print(type(flag_bit))
            if flag_bit in GROUP_NAMES and flag_bit != b'\x00':  # G TODO
                # print('%s\t%s\t%s' % (name, 'G', GROUP_NAMES[flag_bit]))
                msg += '%s\t%s\t%s' % (name, 'G', GROUP_NAMES[flag_bit]) + '\n'
                pass
            elif flag_bit in UNIQUE_NAMES and flag_bit != b'\x00':  # U 
                # print('%s\t%s\t%s' % (name, 'U', UNIQUE_NAMES[flag_bit]))
                msg += '%s\t%s\t%s' % (name, 'U', UNIQUE_NAMES[flag_bit]) + '\n'
                pass
            elif flag_bit in b'\x00':
                name_flags = data[18 * i + 16:18 *i + 18]
                if ord(name_flags[0:1])>=128:
                    group = name.strip()
                    # print('%s\t%s\t%s' % (name, 'G', GROUP_NAMES[flag_bit]))
                    msg += '%s\t%s\t%s' % (name, 'G', GROUP_NAMES[flag_bit]) + '\n'
                else:
                    unique = name
                    # print('%s\t%s\t%s' % (name, 'U', UNIQUE_NAMES[flag_bit]))
                    msg += '%s\t%s\t%s' % (name, 'U', UNIQUE_NAMES[flag_bit]) + '\n'
            else:
                # print('%s\t-\t-' % name)
                msg += '%s\t-\t-' % name + '\n'
                pass
        # print('--------------------------')
        msg += '--------------------------' + '\n'
        # print('%s\\%s' % (group, unique))
        msg = '%s\\%s' % (group, unique) + '\n' + msg

        return { 'group':group, 'unique':unique, 'msg':msg }
    
    except socket.error as e:
        # print(e)
        # print('Fail to Connect to UDP 137')
        return False


def netbios_encode(src):  
    # from http://weaponx.site/2017/06/07/NETBIOS%E4%B8%BB%E6%9C%BA%E5%90%8D%E7%BC%96%E7%A0%81%E7%AE%97%E6%B3%95/
    src = src.ljust(16,"\x20")
    names = []
    for c in src:
        char_ord = ord(c)
        high_4_bits = char_ord >> 4
        low_4_bits = char_ord & 0x0f
        names.append(high_4_bits)
        names.append(low_4_bits)
    
    res = b''
    for name in names:
        # print(name)
        res += chr(0x41 + name).encode()

    return res


def smb_detect(addr, port=139):
    msg = ''

    if port ==139:
        nbns_result = nbns_name(addr)
        if not nbns_result:
            return
        elif not nbns_result['unique']:
            # print('nbns_result_error')
            msg += 'nbns_result_error'
            lock.acquire()
            print(addr + '    ' + msg)
            lock.release()
            return
        # print('%s\\%s' % (nbns_result['group'],nbns_result['unique']))
        msg += nbns_result['msg']

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect((addr, port))
    except Exception as e:
        # print('%s:%d %s' % (addr, port, e))
        lock.acquire()
        print(addr + '    ' + msg)
        lock.release()
        return

    if port == 139:
        name = netbios_encode(nbns_result['unique'])
        # print(name)
        payload0 = b'\x81\x00\x00D ' + name  + b'\x00 EOENEBFACACACACACACACACACACACACA\x00'
        try:
            s.send(payload0)
            s.recv(1024)
        except Exception as e:
            # print('%s:%d %s' % (addr, port, e))
            lock.acquire()
            print(addr + '    ' + msg)
            lock.release()
            return

    
    payload1 = b'\x00\x00\x00\x85\xff\x53\x4d\x42\x72\x00\x00\x00\x00\x18\x53\xc8\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xfe\x00\x00\x00\x00\x00\x62\x00\x02\x50\x43\x20\x4e\x45\x54\x57\x4f\x52\x4b\x20\x50\x52\x4f\x47\x52\x41\x4d\x20\x31\x2e\x30\x00\x02\x4c\x41\x4e\x4d\x41\x4e\x31\x2e\x30\x00\x02\x57\x69\x6e\x64\x6f\x77\x73\x20\x66\x6f\x72\x20\x57\x6f\x72\x6b\x67\x72\x6f\x75\x70\x73\x20\x33\x2e\x31\x61\x00\x02\x4c\x4d\x31\x2e\x32\x58\x30\x30\x32\x00\x02\x4c\x41\x4e\x4d\x41\x4e\x32\x2e\x31\x00\x02\x4e\x54\x20\x4c\x4d\x20\x30\x2e\x31\x32\x00'
    payload2 = b'\x00\x00\x01\x0a\xff\x53\x4d\x42\x73\x00\x00\x00\x00\x18\x07\xc8\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xfe\x00\x00\x40\x00\x0c\xff\x00\x0a\x01\x04\x41\x32\x00\x00\x00\x00\x00\x00\x00\x4a\x00\x00\x00\x00\x00\xd4\x00\x00\xa0\xcf\x00\x60\x48\x06\x06\x2b\x06\x01\x05\x05\x02\xa0\x3e\x30\x3c\xa0\x0e\x30\x0c\x06\x0a\x2b\x06\x01\x04\x01\x82\x37\x02\x02\x0a\xa2\x2a\x04\x28\x4e\x54\x4c\x4d\x53\x53\x50\x00\x01\x00\x00\x00\x07\x82\x08\xa2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x05\x02\xce\x0e\x00\x00\x00\x0f\x00\x57\x00\x69\x00\x6e\x00\x64\x00\x6f\x00\x77\x00\x73\x00\x20\x00\x53\x00\x65\x00\x72\x00\x76\x00\x65\x00\x72\x00\x20\x00\x32\x00\x30\x00\x30\x00\x33\x00\x20\x00\x33\x00\x37\x00\x39\x00\x30\x00\x20\x00\x53\x00\x65\x00\x72\x00\x76\x00\x69\x00\x63\x00\x65\x00\x20\x00\x50\x00\x61\x00\x63\x00\x6b\x00\x20\x00\x32\x00\x00\x00\x00\x00\x57\x00\x69\x00\x6e\x00\x64\x00\x6f\x00\x77\x00\x73\x00\x20\x00\x53\x00\x65\x00\x72\x00\x76\x00\x65\x00\x72\x00\x20\x00\x32\x00\x30\x00\x30\x00\x33\x00\x20\x00\x35\x00\x2e\x00\x32\x00\x00\x00\x00\x00'

    try:
        s.send(payload1)
        s.recv(1024)

        s.send(payload2)

        # TODO handle to rep
        ret = s.recv(1024)
    except Exception as e:
        # print('%s:%d %s' % (addr, port, e))
        lock.acquire()
        print(addr + '    ' + msg)
        lock.release()
        return

    length = ord(ret[43:44]) + ord(ret[44:45]) * 256
    os_version = ret[47 + length:]
    # print(os_version.replace(b'\x00\x00', b'|').replace(b'\x00', b'').decode('UTF-8', errors='ignore'))
    msg += os_version.replace(b'\x00\x00', b'|').replace(b'\x00', b'').decode('UTF-8', errors='ignore') + '\n'

    start = ret.find(b'NTLMSSP')
    # print(ret[start:].replace(b'\x00', b''))

    length = ord(ret[start + 40:start + 41]) + ord(ret[start + 41:start + 42]) * 256 
    # print('length', length)
    # print('max_length', ret[start + 40:start + 44])
    # print('offset', ret[start + 44:start + 48])
    offset = ord(ret[start + 44:start + 45])

    # 中间有 8 位
    # print('Major Version: %d' % ord(ret[start + 48:start + 49]))
    msg += 'Major Version: %d' % ord(ret[start + 48:start + 49]) + '\n'
    # print('Minor Version: %d' % ord(ret[start + 49:start + 50]))
    msg += 'Minor Version: %d' % ord(ret[start + 49:start + 50]) + '\n'
    # print('Bulid Number: %d' %  (ord(ret[start + 50:start + 51]) + 256 * ord(ret[start + 51:start + 52])))
    msg += 'Bulid Number: %d' %  (ord(ret[start + 50:start + 51]) + 256 * ord(ret[start + 51:start + 52])) + '\n'
    # 有 3 字节是空的
    # print('NTLM Current Revision: %d' % (ord(ret[start + 55:start + 56]) ) )
    msg += 'NTLM Current Revision: %d' % (ord(ret[start + 55:start + 56]) ) + '\n' 


    index = start + offset

    while index < start + offset + length:
        item_type = ret[index:index + 2]
        # print('item type', item_type)
        item_length = ord(ret[index + 2:index +3]) + ord(ret[index + 3:index +4]) * 256  
        # print('item length', item_length)
        item_content = ret[index + 4: index + 4 + item_length].replace(b'\x00', b'')
        if item_type == b'\x07\x00':
            
            if sys.version_info[0] == 3:
                timestamp = int.from_bytes(item_content, byteorder='little')  # only py > 3.2
            elif sys.version_info[0] == 2:  # for py2 from https://www.aliyun.com/jiaocheng/445198.html 
                timestamp = int(''.join(reversed(item_content)).encode('hex'), 16) 

            # from https://www.e-learn.cn/content/wangluowenzhang/211641
            EPOCH_AS_FILETIME = 116444736000000000;  HUNDREDS_OF_NANOSECONDS = 10000000
            timestamp = datetime.fromtimestamp((timestamp - EPOCH_AS_FILETIME) / HUNDREDS_OF_NANOSECONDS)

            # print('%s: %s' % (NetBIOS_ITEM_TYPE[item_type], timestamp))
            msg += '%s: %s' % (NetBIOS_ITEM_TYPE[item_type], timestamp) + '\n'
        elif item_type in NetBIOS_ITEM_TYPE:
            # print('%s: %s' % (NetBIOS_ITEM_TYPE[item_type], item_content.decode(errors='ignore')))
            msg += '%s: %s' % (NetBIOS_ITEM_TYPE[item_type], item_content.decode(errors='ignore')) + '\n'
        elif item_type == b'\x00\x00':  #  end
            break
        else:
            # print('Unknown: %s' % (item_content))
            msg += 'Unknown: %s' % (item_content) + '\n'
        # print(ret[index + 4 + item_length:])
        index +=  4 + item_length
    
    lock.acquire()
    print(addr + '    ' +  msg)
    lock.release()
 
if len(sys.argv) == 2:
    addrs = to_ips(sys.argv[1])
    threads = [ threading.Thread(target=smb_detect, args=(addr, 139)) for addr in addrs]
    for t in threads:
        t.start()
        # time.sleep(0.1)
    for t in threads:
        t.join()
elif len(sys.argv) == 3:
    addrs = to_ips(sys.argv[1])
    if sys.argv[2] == '139' or sys.argv[2] == '445':
        port = int(sys.argv[2])
        threads = [ threading.Thread(target=smb_detect, args=(addr, port)) for addr in addrs]
        for t in threads:
            t.start()
            # time.sleep(0.01)
        for t in threads:
            t.join()
    else:
        print('https://github.com/iiilin/inbt')
        print('Usage: python inbt.py ip [port 139|445]')
else:
    print('https://github.com/iiilin/inbt')
    print('Usage: python inbt.py ip [port 139|445]')
