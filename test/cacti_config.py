import os
import argparse
import git
import logging as log
import sys
import copy
import subprocess


def get_proj_root(path):
    git_repo = git.Repo(path, search_parent_directories=True)
    git_root = git_repo.git.rev_parse("--show-toplevel")
    return git_root


sys.path.insert(0, get_proj_root("."))

import file_manager as fmg

# must not have the first line empty
cacti_template_config = """\
# size need_data
-size (bytes) {size_byte}
# power gating
-Array Power Gating - "false"
-WL Power Gating - "false"
-CL Power Gating - "false"
-Bitline floating - "false"
-Interconnect Power Gating - "false"
-Power Gating Performance Loss 0.01
# Line size tlb 8, cache 63 need_data
-block size (bytes) {block_size_byte}
# To model Fully Associative cache, set associativity to zero need_data
-associativity {assoc}
-read-write port 1
-exclusive read port 0
-exclusive write port 0
-single ended read ports 0

# Multiple banks connected using a bus
-UCA bank count 1
//-technology (u) 0.014 invalid tech node
-technology (u) 0.022
# following three parameters are meaningful only for main memories
-page size (bits) 4096
-burst length 8
-internal prefetch width 8
# following parameter can have one of five values -- (itrs-hp, itrs-lstp, itrs-lop, lp-dram, comm-dram)
-Data array cell type - "itrs-hp"
# following parameter can have one of three values -- (itrs-hp, itrs-lstp, itrs-lop)
-Data array peripheral type - "itrs-hp"
# following parameter can have one of five values -- (itrs-hp, itrs-lstp, itrs-lop, lp-dram, comm-dram)
-Tag array cell type - "itrs-hp"
# following parameter can have one of three values -- (itrs-hp, itrs-lstp, itrs-lop)
-Tag array peripheral type - "itrs-hp"
# Bus width include data bits and address bits required by the decoder
-output/input bus width 64
# 300-400 in steps of 10
-operating temperature (K) 360

# Type of memory - cache (with a tag array) or ram (scratch ram similar to a register file)
# or main memory (no tag array and every access will happen at a page granularity Ref: CACTI 5.3 report)
-cache type "cache"

# to model special structure like branch target buffers, directory, etc.
# change the tag size parameter
# if you want cacti to calculate the tagbits, set the tag size to "default"
# need_data
-tag size (b) {tag_bits}

# fast - data and tag access happen in parallel
# sequential - data array is accessed after accessing the tag array
# normal - data array lookup and tag access happen in parallel
#          final data block is broadcasted in data array h-tree
#          after getting the signal from the tag array
# need_data
-access mode (normal, sequential, fast) - "{access_mode}"

# DESIGN OBJECTIVE for UCA (or banks in NUCA)
-design objective (weight delay, dynamic power, leakage power, cycle time, area) 0:0:0:100:0

# Percentage deviation from the minimum value
# Ex: A deviation value of 10:1000:1000:1000:1000 will try to find an organization
# that compromises at most 10% delay.
# NOTE: Try reasonable values for % deviation. Inconsistent deviation
# percentage values will not produce any valid organizations. For example,
# 0:0:100:100:100 will try to identify an organization that has both
# least delay and dynamic power. Since such an organization is not possible, CACTI will
# throw an error. Refer CACTI-6 Technical report for more details
-deviate (delay, dynamic power, leakage power, cycle time, area) 20:100000:100000:100000:100000

# Objective for NUCA
-NUCAdesign objective (weight delay, dynamic power, leakage power, cycle time, area) 100:100:0:0:100
-NUCAdeviate (delay, dynamic power, leakage power, cycle time, area) 10:10000:10000:10000:10000

# Set optimize tag to ED or ED^2 to obtain a cache configuration optimized for
# energy-delay or energy-delay sq. product
# Note: Optimize tag will disable weight or deviate values mentioned above
# Set it to NONE to let weight and deviate values determine the
# appropriate cache configuration
-Optimize ED or ED^2 (ED, ED^2, NONE): "ED^2"
# possible_need_data
-Cache model (NUCA, UCA)  - "UCA"

# In order for CACTI to find the optimal NUCA bank value the following
# variable should be assigned 0.
-NUCA bank count 0

# NOTE: for nuca network frequency is set to a default value of
# 5GHz in time.c. CACTI automatically
# calculates the maximum possible frequency and downgrades this value if necessary

# By default CACTI considers both full-swing and low-swing
# wires to find an optimal configuration. However, it is possible to
# restrict the search space by changing the signaling from "default" to
# "fullswing" or "lowswing" type.
-Wire signaling (fullswing, lowswing, default) - "Global_30"

//-Wire inside mat - "global"
-Wire inside mat - "semi-global"
//-Wire outside mat - "global"
-Wire outside mat - "semi-global"

-Interconnect projection - "conservative"

# Contention in network (which is a function of core count and cache level) is one of
# the critical factor used for deciding the optimal bank count value
# core count can be 4, 8, or 16 data
-Core count {core_counts}
-Cache level (L2/L3) - "L{cache_level_num}"

-Add ECC - "true"

//-Print level (DETAILED, CONCISE) - "CONCISE"
-Print level (DETAILED, CONCISE) - "DETAILED"

# for debugging
-Print input parameters - "true"
# force CACTI to model the cache with the
# following Ndbl, Ndwl, Nspd, Ndsam,
# and Ndcm values
-Force cache config - "false"
-Ndwl 1
-Ndbl 1
-Nspd 0
-Ndcm 1
-Ndsam1 0
-Ndsam2 0

#### Default CONFIGURATION values for baseline external IO parameters to DRAM. More details can be found in the CACTI-IO technical report (), especially Chapters 2 and 3.

# Memory Type (D3=DDR3, D4=DDR4, L=LPDDR2, W=WideIO, S=Serial). Additional memory types can be defined by the user in extio_technology.cc, along with their technology and configuration parameters.
-dram_type "DDR3"

# Memory State (R=Read, W=Write, I=Idle  or S=Sleep)
-io state "WRITE"

# Address bus timing. To alleviate the timing on the command and address bus due to high loading (shared across all memories on the channel), the interface allows for multi-cycle timing options.
-addr_timing 1.0 //SDR (half of DQ rate)

# Memory Density (Gbit per memory/DRAM die)
-mem_density 4 Gb //Valid values 2^n Gb

# IO frequency (MHz) (frequency of the external memory interface).
-bus_freq 800 MHz //As of current memory standards (2013), valid range 0 to 1.5 GHz for DDR3, 0 to 533 MHz for LPDDR2, 0 - 800 MHz for WideIO and 0 - 3 GHz for Low-swing differential. However this can change, and the user is free to define valid ranges based on new memory types or extending beyond existing standards for existing dram types.

# Duty Cycle (fraction of time in the Memory State defined above)
-duty_cycle 1.0 //Valid range 0 to 1.0

# Activity factor for Data (0->1 transitions) per cycle (for DDR, need to account for the higher activity in this parameter. E.g. max. activity factor for DDR is 1.0, for SDR is 0.5)
-activity_dq 1.0 //Valid range 0 to 1.0 for DDR, 0 to 0.5 for SDR

# Activity factor for Control/Address (0->1 transitions) per cycle (for DDR, need to account for the higher activity in this parameter. E.g. max. activity factor for DDR is 1.0, for SDR is 0.5)
-activity_ca 0.5 //Valid range 0 to 1.0 for DDR, 0 to 0.5 for SDR, 0 to 0.25 for 2T, and 0 to 0.17 for 3T

# Number of DQ pins
-num_dq 72 //Number of DQ pins. Includes ECC pins.

# Number of DQS pins. DQS is a data strobe that is sent along with a small number of data-lanes so the source synchronous timing is local to these DQ bits. Typically, 1 DQS per byte (8 DQ bits) is used. The DQS is also typucally differential, just like the CLK pin.
-num_dqs 18 //2 x differential pairs. Include ECC pins as well. Valid range 0 to 18. For x4 memories, could have 36 DQS pins.

# Number of CA pins
-num_ca 25 //Valid range 0 to 35 pins.

# Number of CLK pins. CLK is typically a differential pair. In some cases additional CLK pairs may be used to limit the loading on the CLK pin.
-num_clk  2 //2 x differential pair. Valid values: 0/2/4.

# Number of Physical Ranks
-num_mem_dq 2 //Number of ranks (loads on DQ and DQS) per buffer/register. If multiple LRDIMMs or buffer chips exist, the analysis for capacity and power is reported per buffer/register.

# Width of the Memory Data Bus
-mem_data_width 8 //x4 or x8 or x16 or x32 memories. For WideIO upto x128.

# RTT Termination Resistance
-rtt_value 10000

# RON Termination Resistance
-ron_value 34

# Time of flight for DQ
-tflight_value

# Parameter related to MemCAD
# Number of BoBs: 1,2,3,4,5,6,
-num_bobs 1

# Memory System Capacity in GB
-capacity 80

# Number of Channel per BoB: 1,2.
-num_channels_per_bob 1

# First Metric for ordering different design points
-first metric "Cost"
#-first metric "Bandwidth"
#-first metric "Energy"

# Second Metric for ordering different design points
#-second metric "Cost"
-second metric "Bandwidth"
#-second metric "Energy"

# Third Metric for ordering different design points
#-third metric "Cost"
#-third metric "Bandwidth"
-third metric "Energy"


# Possible DIMM option to consider
#-DIMM model "JUST_UDIMM"
#-DIMM model "JUST_RDIMM"
#-DIMM model "JUST_LRDIMM"
-DIMM model "ALL"

#if channels of each bob have the same configurations
#-mirror_in_bob "T"
-mirror_in_bob "F"

#if we want to see all channels/bobs/memory configurations explored
#-verbose "T"
#-verbose "F"


"""


# size in bytes, line size in bytes (tlb 8, cache 64)
# assoc (0 fully-associativity),
# tag_bits (52 tlb, 40 cache)
# access_mode (normal, sequential, fast)
# core_counts (number)
# cache_level (number)
class CactiConfig:
    def __init__(self, comp, level, size_byte, assoc, core_counts):
        self.comp = comp
        self.comp_level = level

        self.core_counts = core_counts
        self.size_byte = size_byte
        self.assoc = assoc
        if "tlb" in comp or "psc" in comp:
            self.set_tlb_params()
        elif "cache" in comp:
            self.set_cache_params()
        else:
            raise ValueError("%s unsupport components" % comp)

        self.config_content = self.fill_out_config()

    def set_tlb_params(self):
        # should be only L2
        self.block_size_byte = 8
        self.tag_bits = 52
        self.access_mode = "normal"
        self.cache_level = 2

    def set_cache_params(self):
        self.block_size_byte = 64
        self.tag_bits = 64
        self.access_mode = "normal"
        self.cache_level = self.comp_level

    def fill_out_config(self):
        cacti_config = copy.deepcopy(cacti_template_config)
        config_content = cacti_config.format(
            size_byte=self.size_byte,
            block_size_byte=self.block_size_byte,
            assoc=self.assoc,
            tag_bits=self.tag_bits,
            access_mode=self.access_mode,
            core_counts=self.core_counts,
            cache_level_num=self.cache_level)
        return config_content

    def write_config(self, config_filepath):
        fmg.write_file(config_filepath, self.config_content)

    def run(self, config_path):
        # get the rat root
        proj_root = get_proj_root("..")
        bin_path = os.path.join("cacti")
        cmd = f"cd ..; ./{bin_path} -infile ./test/{config_path} > /dev/null;"
        log.info("running %s", cmd)
        subprocess.run(cmd, shell=True)