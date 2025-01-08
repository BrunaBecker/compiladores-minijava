.data
newline: .asciiz "\n"
.text
.globl main
main:
    li $t0, 10
    addi $sp, $sp, -4
    sw $t0, 0($sp)
    move $a0, $t1  # Set 'this' for the method call
    jal Fac_ComputeFac
    move $s0, $a0  # Restore 'this'
    move $t0, $v0
    li $v0, 1
    move $a0, $t0
    syscall
# Program exit
    li $v0, 10
    syscall
Fac_ComputeFac:
Fac_ComputeFac:
    addi $sp, $sp, 4  # Restore stack
    sw $ra, 0($sp)      # Save return address
    sw $s0, 4($sp)      # Save current object reference
    sw $s1, 8($sp)      # Save caller's $s1
    move $s0, $a0  # Set 'this' reference for the method
    lw $t0, 12($sp)
    move $t1, $t0  # Save left operand in $t1
    li $t0, 1
    slt $t0, $t1, $t0  # Set $t0 if $t1 < $t0
    beqz $t0, else_0
    li $t0, 1
    sw $t0, -4($sp)
    j end_if_1
else_0:
    lw $t0, 12($sp)
    move $t1, $t0  # Save left operand in $t1
    lw $t0, 12($sp)
    move $t1, $t0  # Save left operand in $t1
    li $t0, 1
    sub $t0, $t1, $t0  # Subtract $t0 from $t1
    addi $sp, $sp, -4
    sw $t0, 0($sp)
    move $a0, $t1  # Set 'this' for the method call
    jal Fac_ComputeFac
    move $s0, $a0  # Restore 'this'
    move $t0, $v0
    mul $t0, $t1, $t0  # Multiply $t1 and $t0
    sw $t0, -4($sp)
end_if_1:
    lw $s0, 4($sp)
    lw $s1, 8($sp)
    lw $ra, 0($sp)
    addi $sp, $sp, 12
    jr $ra
    move $s0, $a0  # Restore 'this'