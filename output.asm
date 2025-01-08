.data
newline: .asciiz "\n"
.text
.globl main
main:
    # Create new object of class Fac
    li $t0, 0  # Placeholder for object reference
    move $t1, $t0  # Save target object
    li $t0, 10
    addi $sp, $sp, -4
    sw $t0, 0($sp)
    jal ComputeFac
    addi $sp, $sp, 4
    move $t0, $v0
    li $v0, 1
    move $a0, $t0
    syscall
# Program exit
    li $v0, 10
    syscall
Fac_ComputeFac:
ComputeFac:
    addi $sp, $sp, -12  # Allocate space for saved registers
    sw $ra, 0($sp)      # Save return address
    sw $s0, 4($sp)      # Save current object reference
    sw $s1, 8($sp)      # Save caller's $s1
    move $s0, $a0  # Set 'this' reference for the method
    lw $t0, 12($sp)
    move $t1, $t0
    li $t0, 1
    slt $t0, $t1, $t0
    beqz $t0, else_0
    li $t0, 1
    sw $t0, -4($sp)
    j end_if_1
else_0:
    lw $t0, 12($sp)
    move $t1, $t0
    move $t0, $s0  # Load 'this' into $t0
    move $t1, $t0  # Save target object
    lw $t0, 12($sp)
    move $t1, $t0
    li $t0, 1
    sub $t0, $t1, $t0
    addi $sp, $sp, -4
    sw $t0, 0($sp)
    jal ComputeFac
    addi $sp, $sp, 4
    move $t0, $v0
    mul $t0, $t1, $t0
    sw $t0, -4($sp)
end_if_1:
    lw $s0, 4($sp)
    lw $s1, 8($sp)
    lw $ra, 0($sp)
    addi $sp, $sp, 12
    jr $ra