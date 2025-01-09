.data
# Global variables and string literals
debug_msg: .asciiz "Debugging output"
const_zero: .word 0  # Constant 0
const_one: .word 1  # Constant 1
array_sep: .asciiz ", "  # Separator for array elements
array_end: .asciiz "\n"  # End of array message

.text
.globl main
# Main Class: Factorial
main:
li $v0, 9  # Syscall for sbrk (memory allocation)
li $a0, 0  # Set allocation size
syscall
move $t0, $v0  # Store allocated address for the object
li $t1, 10  # Load immediate 10
move $a0, $t1  # Pass argument 0
jal Fac_ComputeFac  # Call method 'ComputeFac'
move $t0, $v0  # Store return value
move $a0, $t0  # Move value to $a0 for printing
li $v0, 1  # Print integer syscall
syscall
li $v0, 10  # Exit syscall
syscall
# Class: Fac
# Method: ComputeFac in class Fac
Fac_ComputeFac:
addiu $sp, $sp, -12  # Reserve space for $fp, $ra, and num
sw $fp, 8($sp)       # Save old frame pointer
sw $ra, 4($sp)       # Save return address
sw $a0, 0($sp)       # Save num (parameter)
move $fp, $sp        # Set frame pointer
li $t1, 1            # Load immediate 1
lw $t0, 0($sp)       # Load num from stack
slt $t2, $t0, $t1    # num < 1?
beq $t2, $zero, else_label_1  # If num >= 1, jump to else
li $v0, 1            # Return 1 if num < 1
j end_if_label_1
else_label_1:
lw $t0, 0($sp)       # Load num from stack
sub $a0, $t0, $t1    # Calculate num - 1 for recursive call
jal Fac_ComputeFac   # Recursive call
lw $t0, 0($sp)       # Reload num from stack
mul $v0, $t0, $v0    # Multiply num by recursion result
end_if_label_1:
lw $ra, 4($sp)       # Restore return address
lw $fp, 8($sp)       # Restore old frame pointer
addiu $sp, $sp, 12   # Restore stack pointer
jr $ra               # Return
# Program termination (if needed)
li $v0, 10  # Exit syscall
syscall