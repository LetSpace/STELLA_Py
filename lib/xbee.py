import busio # type:ignore
import digitalio # type:ignore
import board # type:ignore
import time

# How to use:
# 1. Call the constructor and pass the uart channel connected to the radio.
# 2. Call local_at_command() as needed to change radio settings (see datasheet).
# 3. Call transmit_request() to transmit data.
# 4. Call poll(RECEIVE_PACKET) to receive data.

class XBee:
    def __init__(self, uart: busio.UART, reset_pin: digitalio.DigitalInOut | None = None):
        """Constructor.

        Args:
            uart (busio.UART): UART channel connected to the radio.
            reset_pin (board.Pin): Reset pin.
        """
        self.uart = uart
        self.reset_pin = reset_pin
        self.last_frameid = 1
        self.frameids_to_ignore = []
        self.received_frames = []

        self.LOCAL_AT_COMMAND_REQUEST = 0x08
        self.TRANSMIT_REQUEST = 0x10
        self.LOCAL_AT_COMMAND_RESPONSE = 0x88
        self.EXTENDED_TRANSMIT_STATUS = 0x8B
        self.RECEIVE_PACKET = 0x90

        self.BCAST_ADDR = 0x00000000_0000FFFF # Broadcast Address

        if self.reset_pin != None:
            self.reset_pin.value = 0
            time.sleep(0.1)
            self.reset_pin.value = 1
            time.sleep(0.1)

        if uart.in_waiting > 0:
            # print("Clearing garbage in uart buffer. ", end="")
            uart.reset_input_buffer()
        
        self.local_at_command("AP") # Verify connection

    def next_frameid(self) -> int:
        self.last_frameid = self.last_frameid + 1
        if self.last_frameid > 255:
            self.last_frameid = 1
        return self.last_frameid

    def build_frame(self, message: bytearray) -> bytearray:
        sum = 0
        for b in message:
            sum = sum + b

        checksum = 0xFF - (sum & 0xFF)
        length = len(message)

        frame = bytearray()
        frame.append(0x7E) # Start delimiter
        frame.append(length >> 8) # Length MSB
        frame.append(length & 0xFF) # Length LSB
        frame.extend(message)
        frame.append(checksum)

        return frame

    def verify_checksum(self, frame: bytearray) -> bool:
        sum = 0
        for b in frame[3:]:
            sum = sum + b
        
        return (sum & 0xFF) == 0xFF
    
    def receive_frame(self) -> bytearray:
        frame = bytearray()
        
        starttime = time.monotonic()
        while True:
            if time.monotonic() - starttime > 1:
                raise TimeoutError("No Response.")
            
            b = self.uart.read(1)
            if b is not None and b[0] == 0x7E: # Start delimiter
                frame.append(b[0])
                break

        b = self.uart.read(2)
        if b is None or len(b) < 2:
            raise TimeoutError("UART timeout in length section of frame.")
        length = (b[0] << 8) + b[1]
        frame.extend(b)

        b = self.uart.read(length + 1)
        # if b is None or len(b) < length + 1:
        #     raise TimeoutError(f"UART timeout in body of frame ({0 if b is None else len(b)}/{length+1}).\n{b[:20]}")
        frame.extend(b)

        if self.verify_checksum(frame) is False:
            raise ValueError("Frame corrupted (bad checksum).")
        
        return frame

    def poll(self, frame_type: int | None = None, frame_id: int | None = None) -> bytearray | None:
        """Receive any frames waiting in the uart buffer and return the first, or the first that matches a specific frame type and/or ID.

        Returns the frame if one is found, otherwise returns None."""

        # receive all frames
        while self.uart.in_waiting > 0:
            try:
                self.received_frames.append(self.receive_frame())
            except TimeoutError as e:
                print("TimoutError in receive_frame(): " + str(e))
            except ValueError as e:
                print(e)

        # check received frames
        target = None
        frames_to_ignore = []
        for frame in self.received_frames:
            # skip any frameids marked ignore
            if frame[4] in self.frameids_to_ignore:
                frames_to_ignore.append(frame)
                self.frameids_to_ignore.remove(frame[4])
                continue

            if frame_type == None or frame[3] == frame_type: # Right type or don't care
                if frame_id == None or frame[4] == frame_id: # Right ID or don't care
                    target = frame
                    break
        
        # delete ignored frames
        for frame in frames_to_ignore:
            self.received_frames.remove(frame)
        
        if target is not None:
            self.received_frames.remove(target)
        
        return target

    def local_at_command(self, command: str) -> tuple[int, bytearray]:
        """Sends "AT\<command\>" to the XBee. If a parameter is included, it must be as an integer, not ascii (ex: "AP\\x01").

        Args:
            command (str): The command to send, optionally including parameters.
        
        Returns:
            tuple: (Response status, Response data)
        """
        frameid = self.next_frameid()

        message = bytearray()
        message.append(self.LOCAL_AT_COMMAND_REQUEST) # Frame type
        message.append(frameid)
        message.extend(command.encode())

        frame = self.build_frame(message)
        self.uart.write(frame)

        starttime = time.monotonic()
        response = None
        while response == None:
            if time.monotonic() - starttime > 1:
                raise TimeoutError("No Response.")
            response = self.poll(self.LOCAL_AT_COMMAND_RESPONSE, frameid)

        status = response[7]
        data = response[8:-1]

        return (status, data)

    def transmit_request(self, dest_address: int, payload: bytes, wait_for_response: bool = True):
        """Transmits payload to dest_address. Max of NP bytes in payload (default 0x100).
        
        If wait_for_response is true (default), will wait for and return the response from the radio.
        """
        frameid = self.next_frameid()

        message = bytearray()
        message.append(self.TRANSMIT_REQUEST) # Frame type
        message.append(frameid)
        message.extend(dest_address.to_bytes(8, 'big'))
        message.extend((0xFFFE).to_bytes(2, 'big')) # Reserved
        message.append(0) # Broadcast Radius (0 uses the value of NH)
        message.append(0b01000000) # Transmit Options (P2MP)
        message.extend(payload)

        frame = self.build_frame(message)
        self.uart.write(frame)

        if wait_for_response:
            starttime = time.monotonic()
            response = None
            while response == None:
                if time.monotonic() - starttime > 1:
                    raise TimeoutError("No Response.")
                response = self.poll(self.EXTENDED_TRANSMIT_STATUS, frameid)

            retries = response[7]
            status = response[8]

            return (retries, status)
        else:
            self.frameids_to_ignore.append(frameid)
            return None

