import sys
import traceback
from System.Net.Sockets import UdpClient
from System import Array, Byte
from Antmicro.Renode.Time import TimeInterval

TARGET_HOST = "127.0.0.1"
TARGET_PORT = 9000

try:
    udp
except NameError:
    udp = UdpClient()
    udp.Connect(TARGET_HOST, TARGET_PORT)
    sys.stdout.write("[hook] UDP socket connected to %s:%d\n" % (TARGET_HOST, TARGET_PORT))

def _log(msg):
    sys.stdout.write("[hook] %s\n" % msg)

try:
    replyScheduled
except NameError:
    replyScheduled = False

def _u8(x):
    return int(x) & 0xFF

def _u16_le(lo, hi):
    return _u8(lo) | (_u8(hi) << 8)

def parse_comp_pan_hdr(pkt):
    """
    Finds FCF0/FCF1 = (0x61 or 0x41),0x88 and returns (pan, dst, src, seq).
    Works whether pkt starts with PHR or directly with FCF.
    """
    n = pkt.Length
    if n < 10:
        return None

    # Search near the beginning for the FCF pattern
    for start in range(0, min(6, n - 9)):
        fcf0 = _u8(pkt[start])
        fcf1 = _u8(pkt[start + 1])
        if (fcf0 == 0x61 or fcf0 == 0x41) and fcf1 == 0x88:
            seq  = _u8(pkt[start + 2])
            pan  = _u16_le(pkt[start + 3], pkt[start + 4])
            dst  = _u16_le(pkt[start + 5], pkt[start + 6])
            src  = _u16_le(pkt[start + 7], pkt[start + 8])
            return (pan, dst, src, seq)

    return None

def schedule_reply(pan, dst, src, seq, delay_s=0.0):
    global replyScheduled
    if replyScheduled:
        return
    replyScheduled = True

    zid = 0x0001
    dev_id_arr = Array[Byte]([Byte(0) for _ in range(12)])

    # Reply goes back to sender: swap addresses
    reply_dst = src
    reply_src = dst

    # Avoid duplicate filter: bump seq
    reply_seq = (seq + 1) & 0xFF

    def do_reply(_):
        global replyScheduled
        replyScheduled = False
        try:
            self.SendFwlDataRequestEmpty(pan, reply_dst, reply_src, reply_seq, zid, dev_id_arr, True)
            _log("reply: pan=0x%04X dst=0x%04X src=0x%04X seq=0x%02X zid=0x%04X" %
                 (pan, reply_dst, reply_src, reply_seq, zid))
        except Exception as e:
            _log("do_reply EXCEPTION: %s" % e)
            _log(traceback.format_exc())

    machine.ScheduleAction(TimeInterval.FromSeconds(delay_s), do_reply)
    _log("reply scheduled in simulated time: %.3f ms" % (delay_s * 1000.0))

try:
    if packet is None:
        _log("packet is None")
    else:
        sent = udp.Send(packet, packet.Length)
        _log("sent %d bytes to %s:%d" % (sent, TARGET_HOST, TARGET_PORT))

        parsed = parse_comp_pan_hdr(packet)
        if parsed is None:
            _log("could not parse comp-PAN header (expected 61/41 88 ...); not replying")
        else:
            pan, dst, src, seq = parsed
            schedule_reply(pan, dst, src, seq, delay_s=1.000)

except Exception as e:
    _log("EXCEPTION: %s" % e)
    _log(traceback.format_exc())
