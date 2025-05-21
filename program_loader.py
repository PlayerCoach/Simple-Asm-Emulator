from cpu import CPU
from instruction_interfaces import Instruction
from instruction_set import INSTRUCTION_SET



class ProgramLoader:
    def __init__(self, cpu: CPU):
        self.cpu = cpu
        self._labels: list[str, int] = {}
        self._parsed_input: list[str, tuple] = [] # Stores opcode and tuple of components for future validation
        self._program: list[Instruction] = []
        self._line_number = 0


    def load_program(self, program_path: str):
        """
        Load a program from a file into memory.
        Args:
            program_path (str): Path to the program file.
        """
        with open(program_path, 'r') as file:
            for line_content in file:
                self.parse_lines(line_content.strip())
                self._line_number += 1
        self.validate_and_save_program()

    def load_program_from_string(self, program_string: str):
        """
        Load a program from a string into memory.
        Args:
            program_string (str): The program string.
        """
        lines = program_string.strip().split('\n')
        for line_content in lines:
            self.parse_lines(line_content.strip())
            self._line_number += 1
        self.validate_and_save_program()

   
    def parse_lines(self, line: str):
        """
        Load the next instruction into memory and execute it.
        Args:
            line (str): The line of assembly code to load.
        """
        # Parse the line to get the label and components
        line = self.strip_label(line)

        # Get the opcode and delete it from the line
        opcode, _, line = line.partition(' ')
        opcode = opcode.strip()
        line = line.strip()


        if opcode not in INSTRUCTION_SET:
            raise ValueError(f"Unknown instruction: {opcode} (line: {line})")
        
        instruction_class = INSTRUCTION_SET[opcode]

        # Parse the instruction line to get the components

        self._parsed_input.append((opcode,instruction_class.parse(line)))


    def strip_label(self, line:str) -> str:
        """
        Get the label from the line if it exists.
        If label exits than cut it from the original string
        and add it to the label dictionary

        Args:
            line (str) The line of assembly code to check for label
            It is passed through reference 
            

        """
        first, _ , rest = line.partition(' ')
        if first.endswith(':'):
            label = first[:-1]
            self._labels[label] = self._line_number * 4
            return rest.lstrip()
        return line


    def validate_and_save_program(self):
        """
        Load the program into memory.
        """
        valid_registers = self.cpu.get_valid_registers()

        for opcode, components in self._parsed_input:
            instruction_class = INSTRUCTION_SET[opcode]
     
            try:
                # Validate the instruction components
                instruction_class.validate(components, valid_registers, self._labels, self._line_number)
            except Exception as e:
                raise ValueError(f"Invalid instruction: {opcode} with components {components} (line: {self._line_number})") from e
            instruction = instruction_class(*components, label_dict=self._labels)
            self._program.append(instruction)


    def run_program(self, timeout:int|None=None) -> tuple[int, bool]:
        pipeline: list[Instruction | None] = [None] * 5  # IF, ID, EX, MEM, WB
        cycles = 0
        stall:bool = False
        stall_counter = 0
        is_force_stopped:bool = False # Is stopped by timeout in cycles

        while any(pipeline) or self.cpu.get_PC() < len(self._program)*4:

            if timeout is not None and timeout == cycles:
                is_force_stopped = True
                return cycles, is_force_stopped
            
            cycles += 1
            
            
            # --- Write Back Stage ---
            if pipeline[4]:
                pipeline[4].wb(self.cpu)
                stall = False  # Reset stall after WB

            # --- Memory Stage ---
            if pipeline[3]:
                pipeline[3].mem(self.cpu)

            # --- Execute Stage ---
            if pipeline[2]:
                pipeline[2].ex(self.cpu)

            # --- Instruction Decode Stage ---
            if pipeline[1]:
                stall = pipeline[1].id(self.cpu)
                if stall:
                    stall_counter += 1


              # --- Shift Pipeline ---
            if stall:
                # Freeze IF and ID, let EX/MEM/WB shift
                pipeline = [pipeline[0], pipeline[1]] + [None] + pipeline[2:4]
            else:
                # Normal shift
                pipeline = [None] + pipeline[:4]


             # --- Instruction Fetch (after shift) ---
            if not stall and self.cpu.get_PC() < len(self._program)*4:
                pipeline[0] = self._program[self.cpu.get_PC() // 4]
                self.cpu.set_PC(self.cpu.get_PC() + 4)



            # Debugging output (optional)
            # print(f"Cycle {cycles} stall {stall}:")
            # for i, stage in enumerate(['IF', 'ID', 'EX', 'MEM', 'WB']):
            #     instr = pipeline[i]
            #     print(f"  {stage}: {instr}")


        return cycles, is_force_stopped

            


    def print_state(self):
        """
        Print the current state of the program loader.
        """
        print(f"Current line number: {self._line_number}")
        print(f"Labels: {self._labels}")
        print(f"Parsed input: {self._parsed_input}")
        self.print_program()


    def print_program(self):
        """
        Print the current program.
        """
        for instruction in self._program:
            print(instruction)

    def compare_results(self, path:str = "correct_result.txt") -> bool:
        """
        Compare the results of the program with the expected results.
        Args:
            path (str): Path to the file containing the expected results.
        """
        with open(path, 'r') as file:
            expected_results = file.readlines()
        
        # Compare memory contents to expected results

        for line in expected_results:
            addr_part, data_part = line.strip().split(':')
            base_addr = int(addr_part.strip(), 16)
            values = data_part.strip().split()

            for i, val in enumerate(values):
                expected_value = int(val, 16)
                actual_value = self.cpu.read_dword(base_addr + i * 4)
                if actual_value != expected_value:
                    print(f"Mismatch at address {base_addr + i*4:#010x}: expected {expected_value:#010x}, got {actual_value:#010x}")
                    return False
        return True
       