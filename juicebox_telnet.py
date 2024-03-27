from telnetlib import Telnet


class JuiceboxTelnet(object):
    def __init__(self, host, port=2000, timeout=None):
        self.host = host
        self.port = port
        self.connection = None
        self.timeout = timeout

    def __enter__(self):
        self.connection = self.open()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        if self.connection:
            self.connection.close()
        self.connection = None

    def open(self):
        if not self.connection:
            self.connection = Telnet(host=self.host, port=self.port, timeout=self.timeout)
            self.connection.read_until(b">", self.timeout)
        return self.connection

    def list(self):
        tn = self.open()
        tn.write(b"\n")
        tn.read_until(b"> ", self.timeout)
        tn.write(b"list\n")
        tn.read_until(b"list\r\n! ", self.timeout)
        res = tn.read_until(b">", self.timeout)
        lines = str(res[:-3]).split("\\r\\n")
        out = []
        for line in lines[1:]:
            parts = line.split(" ")
            if len(parts) >= 5:
                out.append({"id": parts[1], "type": parts[2], "dest": parts[4]})
        return out

    def get(self, variable):
        tn = self.open()
        tn.write(b"\n")
        tn.read_until(b"> ", self.timeout)
        cmd = f"get {variable}\r\n".encode("ascii")
        tn.write(cmd)
        tn.read_until(cmd, self.timeout)
        res = tn.read_until(b">", self.timeout)
        return {variable: str(res[:-1].strip())}

    def get_all(self):
        tn = self.open()
        tn.write(b"\n")
        tn.read_until(b">", self.timeout)
        cmd = "get all\r\n".encode("ascii")
        tn.write(cmd)
        tn.read_until(cmd, self.timeout)
        res = tn.read_until(b">", self.timeout)
        lines = str(res[:-1]).split("\\r\\n")
        vars = {}
        for line in lines:
            parts = line.split(": ")
            if len(parts) == 2:
                vars[parts[0]] = parts[1]
        return vars

    def stream_close(self, id):
        tn = self.open()
        tn.write(b"\n")
        tn.read_until(b">", self.timeout)
        tn.write(f"stream_close {id}\n".encode("ascii"))
        tn.read_until(b">", self.timeout)

    def udpc(self, host, port):
        tn = self.open()
        tn.write(b"\n")
        tn.read_until(b">", self.timeout)
        tn.write(f"udpc {host} {port}\n".encode("ascii"))
        tn.read_until(b">", self.timeout)

    def save(self):
        tn = self.open()
        tn.write(b"\n")
        tn.read_until(b">", self.timeout)
        tn.write(b"save\n")
        tn.read_until(b">", self.timeout)
