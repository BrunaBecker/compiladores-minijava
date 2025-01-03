.data
newline: .asciiz "\n"
.text
.globl main
main:
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
    # Allocated num at offset -4
    # Allocated num_aux at offset -8
ComputeFac:
    addi $sp, $sp, -4
    sw $ra, 0($sp)
    beqz $t0, else_0
    li $t0, 1
    sw $t0, -8($sp)
    j end_if_1
else_0:
    lw $t0, -4($sp)
    move $t1, $t0
    move $t1, $t0  # Save target object
    lw $t0, -4($sp)
    move $t1, $t0
    li $t0, 1
    sub $t0, $t1, $t0
    addi $sp, $sp, -4
    sw $t0, 0($sp)
    jal ComputeFac
    addi $sp, $sp, 4
    move $t0, $v0
    mul $t0, $t1, $t0
    sw $t0, -8($sp)
end_if_1:
    lw $ra, 0($sp)
    addi $sp, $sp, 4
    jr $ra