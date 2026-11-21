;==============================================================================
;                     Hail Mary Run Script -- Resumable Variant
;==============================================================================

:BEGINMODEL
    ModelStep = 'BEGIN MODEL'
    ModelStartTime = currenttime() ;get timestamp

    ;initialize by reading in scenario general and specific parameters
    READ FILE = '_ControlCenter.block'
    READ FILE = '..\..\1_Inputs\0_GlobalData\GeneralParameters.block'

    ;set on error goto parameter (set label to jump to if an error occurs)
    ONRUNERRORGOTO='ONERROR'

    ;delete old prn files
    *(DEL *.PRN)

    ;--- RESUME POINT: change the label below, then re-run. -----------------
    GOTO REQUIRE_START_AT_STEP3_01
    ;--------------------------------------------------------------------------


;####################################################################################################################
;Guard: this driver variant exists ONLY to resume Distribution right after its
;feedback loop converged (see calibration_runs/hail-mary/distribution_tail.s),
;by invoking with `tdmcalib run --start-at STEP3_01` (which rewrites the GOTO
;above to STEP3_01, bypassing this guard). If this label is ever reached, it
;means this driver_script ran WITHOUT that override -- e.g. a plain
;`tdmcalib run --run C75` while calibration_runs/C75.yaml's driver_script is
;still pointed at this file. That would silently skip the real feedback loop
;and produce wrong results, so abort instead. Revert C75.yaml's driver_script
;back to the TDM-provided default once this resume attempt is done.
:REQUIRE_START_AT_STEP3_01
    PROMPT QUESTION='This driver script (__HailMary_resume_at_distribution_tail.s) must only be run with --start-at STEP3_01',
        ANSWER="It was invoked without that override -- aborting instead of silently skipping the Distribution feedback loop. Revert calibration_runs/C75.yaml's driver_script to the TDM default (__HailMary_resumable.s) for any normal run."
    ABORT


;####################################################################################################################
:STEP0
    ModelStep = 'STEP 0 - Pre-Processing'
    BegTime_IP = currenttime() ;get timestamp

:STEP0_A00
    READ FILE = '..\..\2_ModelScripts\0_InputProcessing\a_Setup\0_FolderSetup.s'
:STEP0_A01
    READ FILE = '..\..\2_ModelScripts\0_InputProcessing\a_Setup\1_InputSetup.s'
:STEP0_A02
    if (Run_vizTool=1)
        READ FILE = '..\..\2_ModelScripts\0_InputProcessing\a_Setup\2_vizToolSetup.s'
    endif
:STEP0_A03
    READ FILE = '..\..\2_ModelScripts\0_InputProcessing\a_Setup\3_CheckGeneralParameters.s'
:STEP0_B01
    READ FILE = '..\..\2_ModelScripts\0_InputProcessing\b_SEProcessing\1_DemographicsAnalysis.s'
:STEP0_B02
    READ FILE = '..\..\2_ModelScripts\0_InputProcessing\b_SEProcessing\2_UrbanizationTermTime.s'
:STEP0_C01
    READ FILE = '..\..\2_ModelScripts\0_InputProcessing\c_NetworkProcessing\1_NetProcessor.s'
:STEP0_C02
    READ FILE = '..\..\2_ModelScripts\0_InputProcessing\c_NetworkProcessing\2_FFSkim.s'
:STEP0_C03
    READ FILE = '..\..\2_ModelScripts\0_InputProcessing\c_NetworkProcessing\3_TurnPenalty.s'
:STEP0_C04
    READ FILE = '..\..\2_ModelScripts\0_InputProcessing\c_NetworkProcessing\4_Create_walk_xfer_access_links.s'
:STEP0_C05
    READ FILE = '..\..\2_ModelScripts\0_InputProcessing\c_NetworkProcessing\5_WalkTransitSkim_Emp30MinTransit.s'
:STEP0_D01
    READ FILE = '..\..\2_ModelScripts\0_InputProcessing\d_TripTable\1_SpecialTripTable.s'
    if (Run_vizTool=1)
        READ FILE = '..\..\2_ModelScripts\0_InputProcessing\d_TripTable\1_SpecialTripTable_vizTool.s'
    endif
:STEP0_D02
    READ FILE = '..\..\2_ModelScripts\0_InputProcessing\d_TripTable\2_ExternalTripTable.s'
:STEP0_E01
    READ FILE = '..\..\2_ModelScripts\0_InputProcessing\e_TimeOfDayFactors\1_CalculateTimeOfDayFac.s'

    READ FILE = '..\..\2_ModelScripts\0_InputProcessing\a_Setup\_TimeStamp_IP.block' ;report model step run time

;####################################################################################################################
:STEP1
    ModelStep = 'STEP 1 - HH Disaggregation and Auto-Ownership'
    BegTime_AO = currenttime() ;get timestamp

:STEP1_01
    READ FILE = '..\..\2_ModelScripts\1_HHDisag_AutoOwn\1_LifeCycle.s'
:STEP1_02
    READ FILE = '..\..\2_ModelScripts\1_HHDisag_AutoOwn\2_HHDisaggregation.s'
:STEP1_03
    READ FILE = '..\..\2_ModelScripts\1_HHDisag_AutoOwn\3_AutoOwnership.s'
    if (Run_vizTool=1)
        READ FILE = '..\..\2_ModelScripts\1_HHDisag_AutoOwn\3_AutoOwnership_vizTool.s'
    endif

    READ FILE = '..\..\2_ModelScripts\1_HHDisag_AutoOwn\_TimeStamp_AO.block' ;report model step run time

;####################################################################################################################
:STEP2
    ModelStep = 'STEP 2 - Trip Generation'
    BegTime_TG = currenttime() ;get timestamp

:STEP2_01
    READ FILE = '..\..\2_ModelScripts\2_Tripgen\1_TripGen.s'
:STEP2_02
    READ FILE = '..\..\2_ModelScripts\2_Tripgen\2_TripGen_CV.s'
:STEP2_03
    if (Run_vizTool=1)
        READ FILE = '..\..\2_ModelScripts\2_Tripgen\3_TripGen_vizTool.s'
    endif

    READ FILE = '..\..\2_ModelScripts\2_Tripgen\_TimeStamp_TG.block' ;report model step run time

;####################################################################################################################
:STEP3
    ModelStep = 'STEP 3 - Trip Distribution'
    BegTime_DS = currenttime() ;get timestamp

:STEP3_01
    ;Custom driver variant: resumes Distribution right after the feedback loop
    ;converged/exited, instead of from the top of 1_Distribution.s -- see
    ;custom-tdm-scripts/distribution_tail.s for why this is safe and what it
    ;depends on. Use `tdmcalib run --start-at STEP3_01` with this calibration
    ;run's driver_script pointed at this file for one attempt; never edit
    ;tdm/ to add this behavior there.
    READ FILE = '..\..\..\custom-tdm-scripts\distribution_tail.s'
:STEP3_02
    READ FILE = '..\..\2_ModelScripts\3_Distribute\2_estimateHOTspeedtoll.s'
:STEP3_03
    if (Get_data_for_REMM<>1)
        READ FILE = '..\..\2_ModelScripts\3_Distribute\3_SumToDistricts_GRAVITY.s'
    endif
:STEP3_04
    if (Get_data_for_REMM<>1)
        READ FILE = '..\..\2_ModelScripts\3_Distribute\4_TLF_Distrib_PA.s'
    endif
:STEP3_05
    if (Get_data_for_REMM<>1)
        READ FILE = '..\..\2_ModelScripts\3_Distribute\5_SegmentSummary_Dist.s'
    endif

    READ FILE = '..\..\2_ModelScripts\3_Distribute\_TimeStamp_DS.block' ;report model step run time

;####################################################################################################################
:STEP4
    ModelStep = 'STEP 4 - Mode Choice'
    BegTime_MC = currenttime() ;get timestamp

:STEP4_01
    READ FILE = '..\..\2_ModelScripts\4_ModeChoice\01_Segmnt_TripsByDetailed.s'
:STEP4_02
    READ FILE = '..\..\2_ModelScripts\4_ModeChoice\02_Segmnt_TransitAccessMarkets.s'
:STEP4_03
    READ FILE = '..\..\2_ModelScripts\4_ModeChoice\03_Skim_auto.s'
:STEP4_04
    READ FILE = '..\..\2_ModelScripts\4_ModeChoice\04_Create_drive_access_links.s'
:STEP4_05
    READ FILE = '..\..\2_ModelScripts\4_ModeChoice\05_Skim_Tran.s'
:STEP4_06
    READ FILE = '..\..\2_ModelScripts\4_ModeChoice\06_HBW_logsums.s'
:STEP4_07
    READ FILE = '..\..\2_ModelScripts\4_ModeChoice\07_HBW_dest_choice.s'
:STEP4_08
    READ FILE = '..\..\2_ModelScripts\4_ModeChoice\08_TripTablesByPeriod.s'
:STEP4_09
    READ FILE = '..\..\2_ModelScripts\4_ModeChoice\09_Segmnt_PA_HBbyMC.s'
:STEP4_10
    READ FILE = '..\..\2_ModelScripts\4_ModeChoice\10_ConvertSomeXI2HBW.s'
:STEP4_11
    READ FILE = '..\..\2_ModelScripts\4_ModeChoice\11_MC_HBW_HBO_NHB_HBC.s'
:STEP4_12
    READ FILE = '..\..\2_ModelScripts\4_ModeChoice\12_EstimateHBSchModeShare.s'
:STEP4_13
    READ FILE = '..\..\2_ModelScripts\4_ModeChoice\13_EstimateIMZModeShare.s'
:STEP4_14
    READ FILE = '..\..\2_ModelScripts\4_ModeChoice\14_TripsByMode.s'
    if (Run_vizTool=1)
        READ FILE = '..\..\2_ModelScripts\4_ModeChoice\14_TripsByMode_vizTool.s'
    endif
:STEP4_15
    if (Get_data_for_REMM<>1)
        READ FILE = '..\..\2_ModelScripts\4_ModeChoice\15_AsnTran.s'
    endif
:STEP4_16
    if (Get_data_for_REMM<>1)
        READ FILE = '..\..\2_ModelScripts\4_ModeChoice\16_SharesReport.s'
        if (Run_vizTool=1)
            READ FILE = '..\..\2_ModelScripts\4_ModeChoice\16_SharesReport_vizTool.s'
        endif
    endif
:STEP4_17
    if (Get_data_for_REMM<>1)
        READ FILE = '..\..\2_ModelScripts\4_ModeChoice\17_BoardingsReport.s'
        if (Run_vizTool=1)
            READ FILE = '..\..\2_ModelScripts\4_ModeChoice\17_BoardingsReport_vizTool.s'
        endif
    endif
:STEP4_18
    if (Get_data_for_REMM<>1)
        READ FILE = '..\..\2_ModelScripts\4_ModeChoice\18_SumToDistricts_FinalTripTables.s'
        if (Run_vizTool=1)
            READ FILE = '..\..\2_ModelScripts\4_ModeChoice\18_SumToDistricts_FinalTripTables_vizTool.s'
        endif
    endif

    READ FILE = '..\..\2_ModelScripts\4_ModeChoice\_TimeStamp_MC.block' ;report model step run time

;####################################################################################################################
:STEP5
    ModelStep = 'STEP 5 - Final Assignment'
    BegTime_AS = currenttime() ;get timestamp

:STEP5_01
    if (Get_data_for_REMM<>1)
        READ FILE = '..\..\2_ModelScripts\5_AssignHwy\01_Convert_PA_to_OD.s'
    endif
:STEP5_02
    if (Get_data_for_REMM<>1)
        READ FILE = '..\..\2_ModelScripts\5_AssignHwy\02_Assign_AM_MD_PM_EV.s'
    endif
:STEP5_04
    if (Get_data_for_REMM<>1)
        READ FILE = '..\..\2_ModelScripts\5_AssignHwy\04_SummarizeLoadedNetworks.s'
    endif
:STEP5_05
    if (Get_data_for_REMM<>1)
        READ FILE = '..\..\2_ModelScripts\5_AssignHwy\05_RemoveManagedLanes.s'
    endif
:STEP5_06
    if (Get_data_for_REMM<>1)
        READ FILE = '..\..\2_ModelScripts\5_AssignHwy\06_SegmentSummary.s'
        if (Run_vizTool=1)
            READ FILE = '..\..\2_ModelScripts\5_AssignHwy\06_SegmentSummary_vizTool.s'
        endif
    endif
:STEP5_07
    if (Get_data_for_REMM<>1)
        READ FILE = '..\..\2_ModelScripts\5_AssignHwy\07_PerformFinalNetSkim.s'
    endif
:STEP5_08
    if (Get_data_for_REMM<>1)
        READ FILE = '..\..\2_ModelScripts\5_AssignHwy\08_Access_to_Opportunity.s'
        if (Run_vizTool=1)
            READ FILE = '..\..\2_ModelScripts\5_AssignHwy\08_Access_to_Opportunity_vizTool.s'
        endif
    endif
:STEP5_09
    if (Get_data_for_REMM<>1)
        READ FILE = '..\..\2_ModelScripts\5_AssignHwy\09_TAZ_Based_Metrics.s'
        if (Run_vizTool=1)
            READ FILE = '..\..\2_ModelScripts\5_AssignHwy\09_TAZ_Based_Metrics_vizTool.s'
        endif
    endif

    READ FILE = '..\..\2_ModelScripts\5_AssignHwy\_TimeStamp_AS.block' ;report model step run time

;####################################################################################################################
:STEP6
    ModelStep = 'STEP 6 - REMM Input Preparation'
    BegTime_RM = currenttime() ;get timestamp

    if (Get_data_for_REMM=1)
        READ FILE = '..\..\2_ModelScripts\6_REMM\1_output_Logsum.s'
        READ FILE = '..\..\2_ModelScripts\6_REMM\2_output_Time_Auto_Trans_pk.s'
        READ FILE = '..\..\2_ModelScripts\6_REMM\3_output_LinkVolumeTAZlevel.s'
        READ FILE = '..\..\2_ModelScripts\6_REMM\4_output_Rail_Bus_Stops.s'
        READ FILE = '..\..\2_ModelScripts\6_REMM\5_avgTravelTime_byTAZ.s'
        READ FILE = '..\..\2_ModelScripts\6_REMM\6_Run_Parcel_Vol_Python_Script.s'
    endif
    
    READ FILE = '..\..\2_ModelScripts\6_REMM\_TimeStamp_RM.block' ;report model step run time

;####################################################################################################################
:STEP7
    ModelStep = 'STEP 7 - Post Processing'
    BegTime_PP = currenttime() ;get timestamp

    READ FILE = '..\..\2_ModelScripts\7_PostProcessing\0_DeleteTempFiles.s'
    if (Get_data_for_REMM<>1)
        ;READ FILE = '..\..\2_ModelScripts\7_PostProcessing\1_VMTproducedByTAZ.s'
    endif

    ;BCA summary scripts -- for benefit-cost analysis reporting.
    ;Disabled by default, uncomment to include in this run.
    ;READ FILE = '..\..\2_ModelScripts\7_PostProcessing\4_BCA_Summaries\01_Summarize_VehTrips.s'
    ;READ FILE = '..\..\2_ModelScripts\7_PostProcessing\4_BCA_Summaries\02_Summarize_HighwayNet.s'
    ;READ FILE = '..\..\2_ModelScripts\7_PostProcessing\4_BCA_Summaries\03_Summarize_PopEmpAccess.s'
    ;READ FILE = '..\..\2_ModelScripts\7_PostProcessing\5_TDM2MOVES_Prep\01_Calculate_Factors_VMT.s'

    READ FILE = '..\..\2_ModelScripts\7_PostProcessing\_TimeStamp_PP.block' ;report model step run time

:ENDMODEL
    READ FILE = '..\..\2_ModelScripts\_TimeStamp_ModelSuccess.block' ;report model step run time
    ;if (Run_vizTool=1)
    ;    READ FILE = '..\..\2_ModelScripts\7_PostProcessing\2_OpenVizTool.s'
    ;endif

    ;*(echo msgbox "Model Run Completed Successfully!", 0, "OpenPaths CUBE" > SuccessPopup.vbs)
    ;*(wscript SuccessPopup.vbs)
    ;*(del SuccessPopup.vbs)

    Exit ;quit model run

;if an error occurs the process jumps to this location
:ONERROR
    READ FILE = '..\..\2_ModelScripts\_TimeStamp_ModelCrashed.block' ;report model step run time

    ;*(echo msgbox "Model CRASHED! (Return Code 2)", 16, "OpenPaths CUBE ERROR" > "%TEMP%\CrashPopup.vbs")
    ;*(start /wait wscript "%TEMP%\CrashPopup.vbs")
    ;*(del "%TEMP%\CrashPopup.vbs")
