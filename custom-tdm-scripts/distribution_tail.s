;==============================================================================
; Distribution feedback-loop tail
;==============================================================================
; Resumes a crashed C75 (or similarly-structured) run immediately after the
; Distribution feedback loop (LOOP n=1,10 .. ENDLOOP in
; tdm/2_ModelScripts/3_Distribute/1_Distribution.s) has already converged and
; exited via BREAK, so the already-completed feedback-loop iterations are not
; re-run. Content below is copied verbatim from that file (post-ENDLOOP section,
; through end of file) -- never edit tdm/ itself to produce this; re-extract
; the same way if the TDM pins to a tdm_ref where this section has changed.
;
; Depends only on: _ControlCenter.block / GeneralParameters.block macros (always
; read before any HailMary step label -- not set by STEP0-STEP2 or by the loop
; itself), plus files the feedback loop already wrote under
; Temp\3_Distribute\ and 3_Distribute\ for the iteration number set below.
; Verified self-contained by inspection -- no variables from inside the loop
; body are referenced here.
;==============================================================================

; loop-exit state this run reached (normally set by LOOP n=1,10 / BREAK in
; 1_Distribution.s -- set manually here since that loop is not re-run):
n                 = 4   ;last feedback loop iteration that actually ran
n_1               = 3
n_2               = 2
FB_Loop_Converged = 1   ;convergence criteria (PctMatConv & NetConv both >=0.95) were met after loop 4

; only used for this file's own 'Total Distribution' runtime print below --
; that figure will under-report real elapsed time since the loop itself is excluded
ScriptStartTime = currenttime()



;reset n to max iterations if no convergence reached
if (FB_Loop_Converged=0)  n=n-1




;SUMMARIZE FINAL NET AND TRIP TABLE MATRACIES ==============================================================================================

;get start time
SubScriptStartTime_FN = currenttime()


;Cluster: distribute NETWORK call onto processor 2
DistributeMultiStep Alias='FinNet_Proc2'
    
    ;copy distribution network from temp folder
    RUN PGM=NETWORK  MSG='Distribution: Copy Distribution Network from Temp Folder'
    FILEI NETI = '@ScenarioDir@\Temp\3_Distribute\Iter_@n@_convg.net'
    
    FILEO NODEO = '@ScenarioDir@\3_Distribute\Distrib_Node_tmp.dbf'
    
    FILEO LINKO = '@ScenarioDir@\3_Distribute\Distrib_Link_tmp.dbf',
        INCLUDE=A               ,
                B               ,
                DISTANCE        ,
                STREET          ,
                ONEWAY          ,
                EXTERNAL        ,
                LANES           ,
                FT              ,
                SFAC(10.3)      ,
                CFAC(10.3)      ,
                TRK_RSTRCT      ,
                HOV_LYEAR       ,
                Op_Proj         ,
                Rel_Ln          ,

                LINKID          ,
                TAZID           ,
                SEGID(20)       ,
                SUBAREAID       ,
                HOT_ZONEID      ,
                HOT_CHRGPT      ,
                RMPGPID         ,
                MANFWYID        ,
                
                FTCLASS         ,
                URBANVAL        ,
                AREATYPE        ,
                ATYPENAME       ,
                ATYPEGRP        ,
                LANE_MILE       ,
                ANGLE           ,
                DIRECTION       ,
                IB_OB           ,
                PkDirPrd        ,
                @AddLinkFields@ ,
                
                CO_TAZID        ,
                CO_FIPS         ,
                CO_NAME(20)     ,
                CITY_FIPS       ,
                CITY_UGRC       ,
                CITY_NAME(40)   ,
                DISTLRG         ,
                DLRG_NAME(60)   ,
                DISTMED         ,
                DMED_NAME(60)   ,
                DISTSML         ,
                DSML_NAME(60)   ,
                REMM            ,
                CBD             ,
                
                CAP1HR1LN       ,
                RelCap1Hr       ,
                AM_CAP          ,
                MD_CAP          ,
                PM_CAP          ,
                EV_CAP          ,
                AdHOVCap1H      ,
                
                FF_RAMPPEN      ,
                AM_RAMPPEN      ,
                MD_RAMPPEN      ,
                PM_RAMPPEN      ,
                EV_RAMPPEN      ,
                DY_RAMPPEN      ,
                
                HOT_CHRGAM      ,
                HOT_CHRGMD      ,
                HOT_CHRGPM      ,
                HOT_CHRGEV      ,
                
                AM_VOL(10.1)    ,
                MD_VOL(10.1)    ,
                PM_VOL(10.1)    ,
                EV_VOL(10.1)    ,
                DY_VOL(10.1)    ,
                DY_VOL2WY(10.1) ,
                DY_1k(10.1)     ,
                DY_1k_2wy(10.1) ,
                
                AM_VC(10.3)     ,
                MD_VC(10.3)     ,
                PM_VC(10.3)     ,
                EV_VC(10.3)     ,
                
                FF_SPD(10.1)    ,
                AM_SPD(10.1)    ,
                MD_SPD(10.1)    ,
                PM_SPD(10.1)    ,
                EV_SPD(10.1)    ,
                DY_SPD(10.1)    ,
                FF_TkSpd_M(10.1),
                AM_TkSpd_M(10.1),
                MD_TkSpd_M(10.1),
                PM_TkSpd_M(10.1),
                EV_TkSpd_M(10.1),
                DY_TkSpd_M(10.1),
                FF_TkSpd_H(10.1),
                AM_TkSpd_H(10.1),
                MD_TkSpd_H(10.1),
                PM_TkSpd_H(10.1),
                EV_TkSpd_H(10.1),
                DY_TkSpd_H(10.1),
                
                FF_TIME(10.4)   ,
                AM_TIME(10.4)   ,
                MD_TIME(10.4)   ,
                PM_TIME(10.4)   ,
                EV_TIME(10.4)   ,
                DY_TIME(10.4)   ,
                FF_TkTme_M(10.4),
                AM_TkTme_M(10.4),
                MD_TkTme_M(10.4),
                PM_TkTme_M(10.4),
                EV_TkTme_M(10.4),
                DY_TkTme_M(10.4),
                FF_TkTme_H(10.4),
                AM_TkTme_H(10.4),
                MD_TkTme_H(10.4),
                PM_TkTme_H(10.4),
                EV_TkTme_H(10.4),
                DY_TkTme_H(10.4),
                
                AM_VMT(10.2)    ,
                MD_VMT(10.2)    ,
                PM_VMT(10.2)    ,
                EV_VMT(10.2)    ,
                DY_VMT(10.2)    ,
                
                FF_VHT(10.2)    ,
                AM_VHT(10.2)    ,
                MD_VHT(10.2)    ,
                PM_VHT(10.2)    ,
                EV_VHT(10.2)    ,
                DY_VHT(10.2)    ,
                
                AM_DELAY(10.3)  ,
                MD_DELAY(10.3)  ,
                PM_DELAY(10.3)  ,
                EV_DELAY(10.3)  ,
                DY_DELAY(10.3)  ,
                
                FF_BTI_TME(10.2),
                AM_BTI_TME(10.2),
                MD_BTI_TME(10.2),
                PM_BTI_TME(10.2),
                EV_BTI_TME(10.2),
                DY_BTI_TME(10.2),
                
                byGenPurp_      ,
                AM_PER(10.1)    ,
                AM_EXT(10.1)    ,
                AM_CV(10.1)     ,
                AM_TRK(10.1)    ,
                AM_TOT_GEN(10.1),
                MD_PER(10.1)    ,
                MD_EXT(10.1)    ,
                MD_CV(10.1)     ,
                MD_TRK(10.1)    ,
                MD_TOT_GEN(10.1),
                PM_PER(10.1)    ,
                PM_EXT(10.1)    ,
                PM_CV(10.1)     ,
                PM_TRK(10.1)    ,
                PM_TOT_GEN(10.1),
                EV_PER(10.1)    ,
                EV_EXT(10.1)    ,
                EV_CV(10.1)     ,
                EV_TRK(10.1)    ,
                EV_TOT_GEN(10.1),
                DY_PER(10.1)    ,
                DY_EXT(10.1)    ,
                DY_CV(10.1)     ,
                DY_TRK(10.1)    ,
                DY_TOT_GEN(10.1),
                
                byPURP____      ,
                AM_WRK(10.1)    ,
                AM_HBSHp(10.1)  ,
                AM_HBOth(10.1)  ,
                AM_HBS_P(10.1)  ,
                AM_HBS_S(10.1)  ,
                AM_HBC(10.1)    ,
                AM_NHBW(10.1)   ,
                AM_NHBNW(10.1)  ,
                AM_IX(10.1)     ,
                AM_XI(10.1)     ,
                AM_XX(10.1)     ,
                AM_SLT(10.1)    ,
                AM_SMD(10.1)    ,
                AM_SHV(10.1)    ,
                AM_LMD(10.1)    ,
                AM_LHV(10.1)    ,
                AM_TOT_PUR(10.1),
                
                MD_WRK(10.1)    ,
                MD_HBSHp(10.1)  ,
                MD_HBOth(10.1)  ,
                MD_HBS_P(10.1)  ,
                MD_HBS_S(10.1)  ,
                MD_HBC(10.1)    ,
                MD_NHBW(10.1)   ,
                MD_NHBNW(10.1)  ,
                MD_IX(10.1)     ,
                MD_XI(10.1)     ,
                MD_XX(10.1)     ,
                MD_SLT(10.1)    ,
                MD_SMD(10.1)    ,
                MD_SHV(10.1)    ,
                MD_LMD(10.1)    ,
                MD_LHV(10.1)    ,
                MD_TOT_PUR(10.1),
                
                PM_WRK(10.1)    ,
                PM_HBSHp(10.1)  ,
                PM_HBOth(10.1)  ,
                PM_HBS_P(10.1)  ,
                PM_HBS_S(10.1)  ,
                PM_HBC(10.1)    ,
                PM_NHBW(10.1)   ,
                PM_NHBNW(10.1)  ,
                PM_IX(10.1)     ,
                PM_XI(10.1)     ,
                PM_XX(10.1)     ,
                PM_SLT(10.1)    ,
                PM_SMD(10.1)    ,
                PM_SHV(10.1)    ,
                PM_LMD(10.1)    ,
                PM_LHV(10.1)    ,
                PM_TOT_PUR(10.1),
                
                EV_WRK(10.1)    ,
                EV_HBSHp(10.1)  ,
                EV_HBOth(10.1)  ,
                EV_HBS_P(10.1)  ,
                EV_HBS_S(10.1)  ,
                EV_HBC(10.1)    ,
                EV_NHBW(10.1)   ,
                EV_NHBNW(10.1)  ,
                EV_IX(10.1)     ,
                EV_XI(10.1)     ,
                EV_XX(10.1)     ,
                EV_SLT(10.1)    ,
                EV_SMD(10.1)    ,
                EV_SHV(10.1)    ,
                EV_LMD(10.1)    ,
                EV_LHV(10.1)    ,
                EV_TOT_PUR(10.1),
                
                DY_WRK(10.1)    ,
                DY_HBSHp(10.1)  ,
                DY_HBOth(10.1)  ,
                DY_HBS_P(10.1)  ,
                DY_HBS_S(10.1)  ,
                DY_HBC(10.1)    ,
                DY_NHBW(10.1)   ,
                DY_NHBNW(10.1)  ,
                DY_IX(10.1)     ,
                DY_XI(10.1)     ,
                DY_XX(10.1)     ,
                DY_SLT(10.1)    ,
                DY_SMD(10.1)    ,
                DY_SHV(10.1)    ,
                DY_LMD(10.1)    ,
                DY_LHV(10.1)    ,
                DY_TOT_PUR(10.1),
                
                AM_TUNIQUE(10.1),
                MD_TUNIQUE(10.1),
                PM_TUNIQUE(10.1),
                EV_TUNIQUE(10.1),
                AM_TelHBW(10.1) ,
                MD_TelHBW(10.1) ,
                PM_TelHBW(10.1) ,
                EV_TelHBW(10.1) ,
                AM_TelNHBW(10.1),
                MD_TelNHBW(10.1),
                PM_TelNHBW(10.1),
                EV_TelNHBW(10.1)
            
        ZONES   = @Usedzones@

    ENDRUN



    ;write calibration diagnostic output with daily internal MD/HV truck purpose volumes and VMT
    RUN PGM=NETWORK  MSG='Distribution: Output Truck Purpose VMT Diagnostics'
    FILEI NETI = '@ScenarioDir@\Temp\3_Distribute\Iter_@n@_convg.net'

    FILEO LINKO = '@ScenarioDir@\3_Distribute\Distrib_TruckPurposeVMT.dbf',
        INCLUDE=A               ,
                B               ,
                LINKID          ,
                SEGID(20)       ,
                DISTANCE        ,
                FT              ,
                FTCLASS         ,
                CO_FIPS         ,
                CO_NAME(20)     ,
                EXTERNAL        ,

                DY_SMD(10.1)    ,
                DY_SHV(10.1)    ,
                DY_LMD(10.1)    ,
                DY_LHV(10.1)    ,

                DY_MD_D2D(10.1) ,
                DY_MD_HNS(10.1) ,
                DY_MD_LCL(10.1) ,
                DY_MD_REG(10.1) ,
                DY_MD_LHL(10.1) ,
                DY_MD_UNK(10.1) ,
                DY_HV_D2D(10.1) ,
                DY_HV_HNS(10.1) ,
                DY_HV_LCL(10.1) ,
                DY_HV_REG(10.1) ,
                DY_HV_LHL(10.1) ,
                DY_HV_UNK(10.1) ,

                VMT_MD_D2D(12.2),
                VMT_MD_HNS(12.2),
                VMT_MD_LCL(12.2),
                VMT_MD_REG(12.2),
                VMT_MD_LHL(12.2),
                VMT_MD_UNK(12.2),
                VMT_HV_D2D(12.2),
                VMT_HV_HNS(12.2),
                VMT_HV_LCL(12.2),
                VMT_HV_REG(12.2),
                VMT_HV_LHL(12.2),
                VMT_HV_UNK(12.2)

        ZONES   = @Usedzones@

    ENDRUN

;Cluster: end of group distributed to processor 2
EndDistributeMULTISTEP





;Cluster: keep processing on processor 1 (Main)
    ;copy final PA table to Do directory
    RUN PGM=MATRIX  MSG='Distribution: Summarize Final PA Trip Table'
    
        ;copy out averaged P/A matrices (for use in Mode Choice or Assign w/o Mode Choice)
        FILEI MATI[1]='@ScenarioDir@\Temp\3_Distribute\pa_AllPurp_@n@_tmp.mtx' 
              
        FILEO MATO[1]='@ScenarioDir@\3_Distribute\PA_AllPurp_GRAVITY.mtx',
            mo=100-116, 120-124, 130-133, 161-178, 141-146,
            name=TOT      ,
                 HBW      ,
                 HBShp    ,
                 HBOth    ,
                 HBSch_Pr ,
                 HBSch_Sc ,
                 HBC      ,
                 NHBW     ,
                 NHBNW    ,
                 IX       ,
                 XI       ,
                 XX       ,
                 II_LT    ,
                 II_MD    ,
                 II_HV    ,
                 Ext_MD   ,
                 Ext_HV   ,
                 
                 HBSch    ,
                 HBO      ,
                 NHB      ,
                 TTUNIQUE ,
                 HBOthnTT ,
                 
                 Tot_HBW  ,
                 Tel_HBW  ,
                 Tot_NHBW ,
                 Tel_NHBW ,
                 
                 II_LT_D2D,
                 II_LT_HnS,
                 II_LT_Lcl,
                 II_LT_Reg,
                 II_LT_LHl,
                 II_LT_Unk,
                 II_MD_D2D,
                 II_MD_HnS,
                 II_MD_Lcl,
                 II_MD_Reg,
                 II_MD_LHl,
                 II_MD_Unk,
                 II_HV_D2D,
                 II_HV_HnS,
                 II_HV_Lcl,
                 II_HV_Reg,
                 II_HV_LHl,
                 II_HV_Unk,
                 
                 IX_MD    ,
                 XI_MD    ,
                 XX_MD    ,
                 IX_HV    ,
                 XI_HV    ,
                 XX_HV    
        
             RECO[1]='@ScenarioDir@\3_Distribute\_checkPABalance.dbf', 
                 FORM=10.1,
                 FIELDS=Z(10.0),
                      TotPer_P,    TotPer_A,
                         HBW_P,       HBW_A,
                       HBShp_P,     HBShp_A,
                       HBOth_P,     HBOth_A,
                     HBSchPr_P,   HBSchPr_A,
                     HBSchSc_P,   HBSchSc_A,
                         HBC_P,       HBC_A,
                        NHBW_P,      NHBW_A,
                       NHBNW_P,     NHBNW_A,
                       
                      TotExt_P,    TotExt_A,
                          IX_P,        IX_A,
                          XI_P,        XI_A,
                          XX_P,        XX_A,
                          
                      TotTrk_P,    TotTrk_A,
                       II_LT_P,     II_LT_A,
                       II_MD_P,     II_MD_A,
                       II_HV_P,     II_HV_A,
                      Ext_MD_P,    Ext_MD_A,
                      Ext_HV_P,    Ext_HV_A,
                      
                       HBSch_P,     HBSch_A,
                         HBO_P,       HBO_A,
                         NHB_P,       NHB_A,
                    TTUNIQUE_P,  TTUNIQUE_A,
                    HBOthnTT_P,  HBOthnTT_A,
                        
                     Tot_HBW_P,   Tot_HBW_A,
                     Tel_HBW_P,   Tel_HBW_A,
                    Tot_NHBW_P,  Tot_NHBW_A,
                    Tel_NHBW_P,  Tel_NHBW_A,
                      
                      TG_Per_P,    TG_Per_A,
                     TG_IXXI_P,   TG_IXXI_A,
                      TG_Trk_P,    TG_Trk_A,
                  
                  II_LT_D2D_P,   II_LT_D2D_A, 
                  II_LT_HnS_P,   II_LT_HnS_A,
                  II_LT_Lcl_P,   II_LT_Lcl_A,
                  II_LT_Reg_P,   II_LT_Reg_A,
                  II_LT_LHl_P,   II_LT_LHl_A,
                  II_LT_Unk_P,   II_LT_Unk_A,
                                    
                  II_MD_D2D_P,   II_MD_D2D_A,
                  II_MD_HnS_P,   II_MD_HnS_A,
                  II_MD_Lcl_P,   II_MD_Lcl_A,
                  II_MD_Reg_P,   II_MD_Reg_A,
                  II_MD_LHl_P,   II_MD_LHl_A,
                  II_MD_Unk_P,   II_MD_Unk_A,
                                    
                  II_HV_D2D_P,   II_HV_D2D_A,
                  II_HV_HnS_P,   II_HV_HnS_A,
                  II_HV_Lcl_P,   II_HV_Lcl_A,
                  II_HV_Reg_P,   II_HV_Reg_A,
                  II_HV_LHl_P,   II_HV_LHl_A,
                  II_HV_Unk_P,   II_HV_Unk_A
        
        
        
        ZONES   = @Usedzones@
        ZONEMSG = 10
        
        
        
        ;print status to task monitor window
        PrintProgress = INT((i-FIRSTZONE) / (LASTZONE-FIRSTZONE) * 100)
        PrintProgInc = 1
        
        if (i=FIRSTZONE)
            PRINT PRINTO=0, LIST='Processing: ', PrintProgress(5.0), '%'
            CheckProgress = PrintProgInc
        elseif (PrintProgress=CheckProgress)
            PRINT PRINTO=0, LIST='Processing: ', PrintProgress(5.0), '%'
            CheckProgress = CheckProgress + PrintProgInc
        endif
        
        
        
        ;fill working matrices -------------------------------------------------------------------------------
        mw[100] = mi.1.TOT
        mw[101] = mi.1.HBW
        mw[102] = mi.1.HBShp
        mw[103] = mi.1.HBOth
        mw[104] = mi.1.HBSch_Pr
        mw[105] = mi.1.HBSch_Sc
        mw[106] = mi.1.HBC
        mw[107] = mi.1.NHBW
        mw[108] = mi.1.NHBNW
        mw[109] = mi.1.IX
        mw[110] = mi.1.XI
        mw[111] = mi.1.XX
        mw[112] = mi.1.II_LT
        mw[113] = mi.1.II_MD
        mw[114] = mi.1.II_HV
        mw[115] = mi.1.Ext_MD
        mw[116] = mi.1.Ext_HV
        
        mw[120] = mi.1.HBSch
        mw[121] = mi.1.HBO
        mw[122] = mi.1.NHB
        mw[123] = mi.1.TTUNIQUE
        mw[124] = mi.1.HBOthnTT
        
        mw[130] = mi.1.Tot_HBW
        mw[131] = mi.1.Tel_HBW
        mw[132] = mi.1.Tot_NHBW
        mw[133] = mi.1.Tel_NHBW
                
        mw[141] = mi.1.IX_MD
        mw[142] = mi.1.XI_MD
        mw[143] = mi.1.XX_MD
        mw[144] = mi.1.IX_HV
        mw[145] = mi.1.XI_HV
        mw[146] = mi.1.XX_HV
        
        mw[161] = mi.1.II_LT_D2D
        mw[162] = mi.1.II_LT_HnS
        mw[163] = mi.1.II_LT_Lcl
        mw[164] = mi.1.II_LT_Reg
        mw[165] = mi.1.II_LT_LHl
        mw[166] = mi.1.II_LT_Unk
                          
        mw[167] = mi.1.II_MD_D2D
        mw[168] = mi.1.II_MD_HnS
        mw[169] = mi.1.II_MD_Lcl
        mw[170] = mi.1.II_MD_Reg
        mw[171] = mi.1.II_MD_LHl
        mw[172] = mi.1.II_MD_Unk
                          
        mw[173] = mi.1.II_HV_D2D
        mw[174] = mi.1.II_HV_HnS
        mw[175] = mi.1.II_HV_Lcl
        mw[176] = mi.1.II_HV_Reg
        mw[177] = mi.1.II_HV_LHl
        mw[178] = mi.1.II_HV_Unk
        
        
        mw[200] = mi.1.TOT.T
        mw[201] = mi.1.HBW.T
        mw[202] = mi.1.HBShp.T
        mw[203] = mi.1.HBOth.T
        mw[204] = mi.1.HBSch_Pr.T
        mw[205] = mi.1.HBSch_Sc.T
        mw[206] = mi.1.HBC.T
        mw[207] = mi.1.NHBW.T
        mw[208] = mi.1.NHBNW.T
        mw[209] = mi.1.IX.T
        mw[210] = mi.1.XI.T
        mw[211] = mi.1.XX.T
        mw[212] = mi.1.II_LT.T
        mw[213] = mi.1.II_MD.T
        mw[214] = mi.1.II_HV.T
        mw[215] = mi.1.Ext_MD.T
        mw[216] = mi.1.Ext_HV.T
        
        mw[220] = mi.1.HBSch.T
        mw[221] = mi.1.HBO.T
        mw[222] = mi.1.NHB.T
        mw[223] = mi.1.TTUNIQUE.T
        mw[224] = mi.1.HBOthnTT.T
        
        mw[230] = mi.1.Tot_HBW.T 
        mw[231] = mi.1.Tel_HBW.T 
        mw[232] = mi.1.Tot_NHBW.T
        mw[233] = mi.1.Tel_NHBW.T
        
        mw[261] = mi.1.II_LT_D2D.T
        mw[262] = mi.1.II_LT_HnS.T
        mw[263] = mi.1.II_LT_Lcl.T
        mw[264] = mi.1.II_LT_Reg.T
        mw[265] = mi.1.II_LT_LHl.T
        mw[266] = mi.1.II_LT_Unk.T
                          
        mw[267] = mi.1.II_MD_D2D.T
        mw[268] = mi.1.II_MD_HnS.T
        mw[269] = mi.1.II_MD_Lcl.T
        mw[270] = mi.1.II_MD_Reg.T
        mw[271] = mi.1.II_MD_LHl.T
        mw[272] = mi.1.II_MD_Unk.T
                          
        mw[273] = mi.1.II_HV_D2D.T
        mw[274] = mi.1.II_HV_HnS.T
        mw[275] = mi.1.II_HV_Lcl.T
        mw[276] = mi.1.II_HV_Reg.T
        mw[277] = mi.1.II_HV_LHl.T
        mw[278] = mi.1.II_HV_Unk.T

        
        
        ;calculate P & A row/column sums ---------------------------------------------------------------------
        ;P's
        RO.HBW_P      = rowsum(101)
        RO.HBShp_P    = rowsum(102)
        RO.HBOth_P    = rowsum(103)
        RO.HBSchPr_P  = rowsum(104)
        RO.HBSchSc_P  = rowsum(105)
        RO.HBC_P      = rowsum(106)
        RO.NHBW_P     = rowsum(107)
        RO.NHBNW_P    = rowsum(108)
        RO.IX_P       = rowsum(109)
        RO.XI_P       = rowsum(110)
        RO.XX_P       = rowsum(111)
        RO.II_LT_P    = rowsum(112)
        RO.II_MD_P    = rowsum(113)
        RO.II_HV_P    = rowsum(114)
        RO.Ext_MD_P   = rowsum(115)
        RO.Ext_HV_P   = rowsum(116)
        
        RO.HBSch_P    = rowsum(120)
        RO.HBO_P      = rowsum(121)
        RO.NHB_P      = rowsum(122)
        RO.TTUNIQUE_P = rowsum(123)
        RO.HBOthnTT_P = rowsum(124)
        
        RO.Tot_HBW_P  = rowsum(130)
        RO.Tel_HBW_P  = rowsum(131)
        RO.Tot_NHBW_P = rowsum(132)
        RO.Tel_NHBW_P = rowsum(133)
        
        RO.II_LT_D2D_P = rowsum(161)
        RO.II_LT_HnS_P = rowsum(162)
        RO.II_LT_Lcl_P = rowsum(163)
        RO.II_LT_Reg_P = rowsum(164)
        RO.II_LT_LHl_P = rowsum(165)
        RO.II_LT_Unk_P = rowsum(166)
              
        RO.II_MD_D2D_P = rowsum(167)
        RO.II_MD_HnS_P = rowsum(168)
        RO.II_MD_Lcl_P = rowsum(169)
        RO.II_MD_Reg_P = rowsum(170)
        RO.II_MD_LHl_P = rowsum(171)
        RO.II_MD_Unk_P = rowsum(172)
              
        RO.II_HV_D2D_P = rowsum(173)
        RO.II_HV_HnS_P = rowsum(174)
        RO.II_HV_Lcl_P = rowsum(175)
        RO.II_HV_Reg_P = rowsum(176)
        RO.II_HV_LHl_P = rowsum(177)
        RO.II_HV_Unk_P = rowsum(178)
        
        
        RO.TotPer_P  = RO.HBW_P     +
                       RO.HBShp_P   +
                       RO.HBOth_P   +
                       RO.HBSchPr_P +
                       RO.HBSchSc_P +
                       RO.HBC_P     +
                       RO.NHBW_P    +
                       RO.NHBNW_P   
        
        
        RO.TotExt_P  = RO.IX_P +
                       RO.XI_P +
                       RO.XX_P 
        
        
        RO.TotTrk_P  = RO.II_LT_P  +
                       RO.II_MD_P  +
                       RO.II_HV_P  +
                       RO.Ext_MD_P +
                       RO.Ext_HV_P 
        
        
        RO.TG_Per_P  = RO.Tot_HBW_P  +          ;use HBW with telecommute
                       RO.HBShp_P    +
                       RO.HBOthnTT_P +          ;use HBOth without TTUNIQUE
                       RO.HBSchPr_P  +
                       RO.HBSchSc_P  +
                       RO.HBC_P      +
                       RO.Tot_NHBW_P +          ;use NHBW with telecommute
                       RO.NHBNW_P    
        
        
        RO.TG_IXXI_P = RO.IX_P +                ;exclude XX
                       RO.XI_P 
        
        
        RO.TG_Trk_P  = RO.II_LT_P  +            ;exclude Ext_MD_P & Ext_HV_P
                       RO.II_MD_P  +
                       RO.II_HV_P  
        
        
        ;A's
        RO.HBW_A      = rowsum(201)
        RO.HBShp_A    = rowsum(202)
        RO.HBOth_A    = rowsum(203)
        RO.HBSchPr_A  = rowsum(204)
        RO.HBSchSc_A  = rowsum(205)
        RO.HBC_A      = rowsum(206)
        RO.NHBW_A     = rowsum(207)
        RO.NHBNW_A    = rowsum(208)
        RO.IX_A       = rowsum(209)
        RO.XI_A       = rowsum(210)
        RO.XX_A       = rowsum(211)
        RO.II_LT_A    = rowsum(212)
        RO.II_MD_A    = rowsum(213)
        RO.II_HV_A    = rowsum(214)
        RO.Ext_MD_A   = rowsum(215)
        RO.Ext_HV_A   = rowsum(216)
        
        RO.HBSch_A    = rowsum(220)
        RO.HBO_A      = rowsum(221)
        RO.NHB_A      = rowsum(222)
        RO.TTUNIQUE_A = rowsum(223)
        RO.HBOthnTT_A = rowsum(224)
        
        RO.Tot_HBW_A  = rowsum(230)
        RO.Tel_HBW_A  = rowsum(231)
        RO.Tot_NHBW_A = rowsum(232)
        RO.Tel_NHBW_A = rowsum(233)
        
        RO.II_LT_D2D_A = rowsum(261)
        RO.II_LT_HnS_A = rowsum(262)
        RO.II_LT_Lcl_A = rowsum(263)
        RO.II_LT_Reg_A = rowsum(264)
        RO.II_LT_LHl_A = rowsum(265)
        RO.II_LT_Unk_A = rowsum(266)
              
        RO.II_MD_D2D_A = rowsum(267)
        RO.II_MD_HnS_A = rowsum(268)
        RO.II_MD_Lcl_A = rowsum(269)
        RO.II_MD_Reg_A = rowsum(270)
        RO.II_MD_LHl_A = rowsum(271)
        RO.II_MD_Unk_A = rowsum(272)
              
        RO.II_HV_D2D_A = rowsum(273)
        RO.II_HV_HnS_A = rowsum(274)
        RO.II_HV_Lcl_A = rowsum(275)
        RO.II_HV_Reg_A = rowsum(276)
        RO.II_HV_LHl_A = rowsum(277)
        RO.II_HV_Unk_A = rowsum(278)
        
        
        RO.TotPer_A  = RO.HBW_A     +
                       RO.HBShp_A   +
                       RO.HBOth_A   +
                       RO.HBSchPr_A +
                       RO.HBSchSc_A +
                       RO.HBC_A     +
                       RO.NHBW_A    +
                       RO.NHBNW_A   
        
        
        RO.TotExt_A  = RO.IX_A +
                       RO.XI_A +
                       RO.XX_A 
        
        
        RO.TotTrk_A  = RO.II_LT_A  +
                       RO.II_MD_A  +
                       RO.II_HV_A  +
                       RO.Ext_MD_A +
                       RO.Ext_HV_A 
        
        
        RO.TG_Per_A  = RO.Tot_HBW_A  +          ;use HBW with telecommute
                       RO.HBShp_A    +
                       RO.HBOthnTT_A +          ;use HBOth without TTUNIQUE
                       RO.HBSchPr_A  +
                       RO.HBSchSc_A  +
                       RO.HBC_A      +
                       RO.Tot_NHBW_A +          ;use NHBW with telecommute
                       RO.NHBNW_A    
        
        
        RO.TG_IXXI_A = RO.IX_A +                ;exclude XX
                       RO.XI_A 
        
        
        RO.TG_Trk_A  = RO.II_LT_A  +            ;exclude Ext_MD_A & Ext_HV_A
                       RO.II_MD_A  +
                       RO.II_HV_A   
        
        
        ;write output file
        WRITE RECO=1
        
        
        
        ;calculate matrix totals -----------------------------------------------------------------------------
        ;P's
        sum_HBW_P      = sum_HBW_P      + RO.HBW_P
        sum_HBShp_P    = sum_HBShp_P    + RO.HBShp_P
        sum_HBOth_P    = sum_HBOth_P    + RO.HBOth_P
        sum_HBSchPr_P  = sum_HBSchPr_P  + RO.HBSchPr_P
        sum_HBSchSc_P  = sum_HBSchSc_P  + RO.HBSchSc_P
        sum_HBC_P      = sum_HBC_P      + RO.HBC_P
        sum_NHBW_P     = sum_NHBW_P     + RO.NHBW_P
        sum_NHBNW_P    = sum_NHBNW_P    + RO.NHBNW_P
        sum_IX_P       = sum_IX_P       + RO.IX_P
        sum_XI_P       = sum_XI_P       + RO.XI_P
        sum_XX_P       = sum_XX_P       + RO.XX_P
        sum_II_LT_P    = sum_II_LT_P    + RO.II_LT_P
        sum_II_MD_P    = sum_II_MD_P    + RO.II_MD_P
        sum_II_HV_P    = sum_II_HV_P    + RO.II_HV_P
        sum_Ext_MD_P   = sum_Ext_MD_P   + RO.Ext_MD_P
        sum_Ext_HV_P   = sum_Ext_HV_P   + RO.Ext_HV_P
        
        sum_HBSch_P    = sum_HBSch_P    + RO.HBSch_P
        sum_HBO_P      = sum_HBO_P      + RO.HBO_P
        sum_NHB_P      = sum_NHB_P      + RO.NHB_P
        sum_TTUNIQUE_P = sum_TTUNIQUE_P + RO.TTUNIQUE_P
        sum_HBOthnTT_P = sum_HBOthnTT_P + RO.HBOthnTT_P
        
        sum_Tot_HBW_P  = sum_Tot_HBW_P  + RO.Tot_HBW_P
        sum_Tel_HBW_P  = sum_Tel_HBW_P  + RO.Tel_HBW_P
        sum_Tot_NHBW_P = sum_Tot_NHBW_P + RO.Tot_NHBW_P
        sum_Tel_NHBW_P = sum_Tel_NHBW_P + RO.Tel_NHBW_P
        
        
        sum_TotPer_P  = sum_HBW_P     +
                        sum_HBShp_P   +
                        sum_HBOth_P   +
                        sum_HBSchPr_P +
                        sum_HBSchSc_P +
                        sum_HBC_P     +
                        sum_NHBW_P    +
                        sum_NHBNW_P   
        
        sum_TotExt_P  = sum_IX_P +
                        sum_XI_P +
                        sum_XX_P 
        
        sum_TotTrk_P  = sum_II_LT_P  +
                        sum_II_MD_P  +
                        sum_II_HV_P  +
                        sum_Ext_MD_P +
                        sum_Ext_HV_P 
        
        
        sum_TG_Per_P  = sum_Tot_HBW_P  +          ;use HBW with telecommute
                        sum_HBShp_P    +
                        sum_HBOthnTT_P +          ;use HBOth without TTUNIQUE
                        sum_HBSchPr_P  +
                        sum_HBSchSc_P  +
                        sum_HBC_P      +
                        sum_Tot_NHBW_P +          ;use NHBW with telecommute
                        sum_NHBNW_P    
                    
        sum_TG_IXXI_P = sum_IX_P +                ;exclude XX
                        sum_XI_P 
        
        sum_TG_Trk_P  = sum_II_LT_P  +            ;exclude Ext_MD_P & Ext_HV_P
                        sum_II_MD_P  +
                        sum_II_HV_P   
        
        
        ;A's
        sum_HBW_A      = sum_HBW_A      + RO.HBW_A
        sum_HBShp_A    = sum_HBShp_A    + RO.HBShp_A
        sum_HBOth_A    = sum_HBOth_A    + RO.HBOth_A
        sum_HBSchPr_A  = sum_HBSchPr_A  + RO.HBSchPr_A
        sum_HBSchSc_A  = sum_HBSchSc_A  + RO.HBSchSc_A
        sum_HBC_A      = sum_HBC_A      + RO.HBC_A
        sum_NHBW_A     = sum_NHBW_A     + RO.NHBW_A
        sum_NHBNW_A    = sum_NHBNW_A    + RO.NHBNW_A
        sum_IX_A       = sum_IX_A       + RO.IX_A
        sum_XI_A       = sum_XI_A       + RO.XI_A
        sum_XX_A       = sum_XX_A       + RO.XX_A
        sum_II_LT_A    = sum_II_LT_A    + RO.II_LT_A
        sum_II_MD_A    = sum_II_MD_A    + RO.II_MD_A
        sum_II_HV_A    = sum_II_HV_A    + RO.II_HV_A
        sum_Ext_MD_A   = sum_Ext_MD_A   + RO.Ext_MD_A
        sum_Ext_HV_A   = sum_Ext_HV_A   + RO.Ext_HV_A
        
        sum_HBSch_A    = sum_HBSch_A    + RO.HBSch_A
        sum_HBO_A      = sum_HBO_A      + RO.HBO_A
        sum_NHB_A      = sum_NHB_A      + RO.NHB_A
        sum_TTUNIQUE_A = sum_TTUNIQUE_A + RO.TTUNIQUE_A
        sum_HBOthnTT_A = sum_HBOthnTT_A + RO.HBOthnTT_A
        
        sum_Tot_HBW_A  = sum_Tot_HBW_A  + RO.Tot_HBW_A
        sum_Tel_HBW_A  = sum_Tel_HBW_A  + RO.Tel_HBW_A
        
        sum_Tot_NHBW_A = sum_Tot_NHBW_A + RO.Tot_NHBW_A
        sum_Tel_NHBW_A = sum_Tel_NHBW_A + RO.Tel_NHBW_A
        
        
        sum_TotPer_A  = sum_HBW_A     +
                        sum_HBShp_A   +
                        sum_HBOth_A   +
                        sum_HBSchPr_A +
                        sum_HBSchSc_A +
                        sum_HBC_A     +
                        sum_NHBW_A    +
                        sum_NHBNW_A   
        
        sum_TotExt_A  = sum_IX_A +
                        sum_XI_A +
                        sum_XX_A 
        
        sum_TotTrk_A  = sum_II_LT_A  +
                        sum_II_MD_A  +
                        sum_II_HV_A  +
                        sum_Ext_MD_A +
                        sum_Ext_HV_A 
        
        
        sum_TG_Per_A  = sum_Tot_HBW_A  +          ;use HBW with telecommute
                        sum_HBShp_A    +
                        sum_HBOthnTT_A +          ;use HBOth without TTUNIQUE
                        sum_HBSchPr_A  +
                        sum_HBSchSc_A  +
                        sum_HBC_A      +
                        sum_Tot_NHBW_A +          ;use NHBW with telecommute
                        sum_NHBNW_A    
                    
        sum_TG_IXXI_A = sum_IX_A +                ;exclude XX
                        sum_XI_A 
        
        sum_TG_Trk_A  = sum_II_LT_A  +            ;exclude Ext_MD_A & Ext_HV_A
                        sum_II_MD_A  +
                        sum_II_HV_A   
        
        
        
        ;calculate intrazonal % ------------------------------------------------------------------------------
        if (i=@BoxElderRange@)
            
            total_HBW_BE = total_HBW_BE + rowsum(101)
            total_HBO_BE = total_HBO_BE + rowsum(121)
            total_NHB_BE = total_NHB_BE + rowsum(122)
            
            intrazonal_HBW_BE = intrazonal_HBW_BE + mw[101][i]
            intrazonal_HBO_BE = intrazonal_HBO_BE + mw[121][i]
            intrazonal_NHB_BE = intrazonal_NHB_BE + mw[122][i]
            
        elseif (i=@WeberRange@)
            
            total_HBW_WE = total_HBW_WE + rowsum(101)
            total_HBO_WE = total_HBO_WE + rowsum(121)
            total_NHB_WE = total_NHB_WE + rowsum(122)
            
            intrazonal_HBW_WE = intrazonal_HBW_WE + mw[101][i]
            intrazonal_HBO_WE = intrazonal_HBO_WE + mw[121][i]
            intrazonal_NHB_WE = intrazonal_NHB_WE + mw[122][i]
            
        elseif (i=@DavisRange@)
            
            total_HBW_DA = total_HBW_DA + rowsum(101)
            total_HBO_DA = total_HBO_DA + rowsum(121)
            total_NHB_DA = total_NHB_DA + rowsum(122)
            
            intrazonal_HBW_DA = intrazonal_HBW_DA + mw[101][i]
            intrazonal_HBO_DA = intrazonal_HBO_DA + mw[121][i]
            intrazonal_NHB_DA = intrazonal_NHB_DA + mw[122][i]
            
        elseif (i=@SLRange@)
            
            total_HBW_SL = total_HBW_SL + rowsum(101)
            total_HBO_SL = total_HBO_SL + rowsum(121)
            total_NHB_SL = total_NHB_SL + rowsum(122)
            
            intrazonal_HBW_SL = intrazonal_HBW_SL + mw[101][i]
            intrazonal_HBO_SL = intrazonal_HBO_SL + mw[121][i]
            intrazonal_NHB_SL = intrazonal_NHB_SL + mw[122][i]
            
        elseif (i=@UtahRange@)
            
            total_HBW_UT = total_HBW_UT + rowsum(101)
            total_HBO_UT = total_HBO_UT + rowsum(121)
            total_NHB_UT = total_NHB_UT + rowsum(122)
            
            intrazonal_HBW_UT = intrazonal_HBW_UT + mw[101][i]
            intrazonal_HBO_UT = intrazonal_HBO_UT + mw[121][i]
            intrazonal_NHB_UT = intrazonal_NHB_UT + mw[122][i]
            
        endif
        
        
        
        if (i=ZONES)
            
            ;calculate regional totals
            total_HBW_RE = total_HBW_BE +
                           total_HBW_WE +
                           total_HBW_DA +
                           total_HBW_SL +
                           total_HBW_UT
                         
            total_HBO_RE = total_HBO_BE +
                           total_HBO_WE +
                           total_HBO_DA +
                           total_HBO_SL +
                           total_HBO_UT
                         
            total_NHB_RE = total_NHB_BE +
                           total_NHB_WE +
                           total_NHB_DA +
                           total_NHB_SL +
                           total_NHB_UT
            
            
            intrazonal_HBW_RE = intrazonal_HBW_BE +
                                intrazonal_HBW_WE +
                                intrazonal_HBW_DA +
                                intrazonal_HBW_SL +
                                intrazonal_HBW_UT
                              
            intrazonal_HBO_RE = intrazonal_HBO_BE +
                                intrazonal_HBO_WE +
                                intrazonal_HBO_DA +
                                intrazonal_HBO_SL +
                                intrazonal_HBO_UT
                              
            intrazonal_NHB_RE = intrazonal_NHB_BE +
                                intrazonal_NHB_WE +
                                intrazonal_NHB_DA +
                                intrazonal_NHB_SL +
                                intrazonal_NHB_UT
            
            
            ;calculate introzonal %
            if (total_HBW_RE>0)  pct_intrazonal_HBW_RE = intrazonal_HBW_RE / total_HBW_RE * 100
            if (total_HBW_BE>0)  pct_intrazonal_HBW_BE = intrazonal_HBW_BE / total_HBW_BE * 100
            if (total_HBW_WE>0)  pct_intrazonal_HBW_WE = intrazonal_HBW_WE / total_HBW_WE * 100
            if (total_HBW_DA>0)  pct_intrazonal_HBW_DA = intrazonal_HBW_DA / total_HBW_DA * 100
            if (total_HBW_SL>0)  pct_intrazonal_HBW_SL = intrazonal_HBW_SL / total_HBW_SL * 100
            if (total_HBW_UT>0)  pct_intrazonal_HBW_UT = intrazonal_HBW_UT / total_HBW_UT * 100
            
            if (total_HBO_RE>0)  pct_intrazonal_HBO_RE = intrazonal_HBO_RE / total_HBO_RE * 100
            if (total_HBO_BE>0)  pct_intrazonal_HBO_BE = intrazonal_HBO_BE / total_HBO_BE * 100
            if (total_HBO_WE>0)  pct_intrazonal_HBO_WE = intrazonal_HBO_WE / total_HBO_WE * 100
            if (total_HBO_DA>0)  pct_intrazonal_HBO_DA = intrazonal_HBO_DA / total_HBO_DA * 100
            if (total_HBO_SL>0)  pct_intrazonal_HBO_SL = intrazonal_HBO_SL / total_HBO_SL * 100
            if (total_HBO_UT>0)  pct_intrazonal_HBO_UT = intrazonal_HBO_UT / total_HBO_UT * 100
            
            if (total_NHB_RE>0)  pct_intrazonal_NHB_RE = intrazonal_NHB_RE / total_NHB_RE * 100
            if (total_NHB_BE>0)  pct_intrazonal_NHB_BE = intrazonal_NHB_BE / total_NHB_BE * 100
            if (total_NHB_WE>0)  pct_intrazonal_NHB_WE = intrazonal_NHB_WE / total_NHB_WE * 100
            if (total_NHB_DA>0)  pct_intrazonal_NHB_DA = intrazonal_NHB_DA / total_NHB_DA * 100
            if (total_NHB_SL>0)  pct_intrazonal_NHB_SL = intrazonal_NHB_SL / total_NHB_SL * 100
            if (total_NHB_UT>0)  pct_intrazonal_NHB_UT = intrazonal_NHB_UT / total_NHB_UT * 100
            
            
            
            ;print output ------------------------------------------------------------------------------------
            PRINT FILE='@ScenarioDir@\_Log\_LogFile.txt', 
            APPEND=T,  
            FORM=13.0C,
            LIST='\n',
                 '\n',
                 '\nDistribution - Trip Summary',
                 '\n',
                 '\n  Matrix Totals',
                 '\n              ',  '  Productions',  '  Attractions',  ' P/A Balance ',
                 '\n    TotPer    ',   sum_TotPer_P  ,   sum_TotPer_A  ,   sum_TotPer_P/sum_TotPer_A(10.2)    ,
                 '\n      HBW     ',   sum_HBW_P     ,   sum_HBW_A     ,   sum_HBW_P/sum_HBW_A(10.2)          ,
                 '\n      HBShp   ',   sum_HBShp_P   ,   sum_HBShp_A   ,   sum_HBShp_P/sum_HBShp_A(10.2)      ,
                 '\n      HBOth   ',   sum_HBOth_P   ,   sum_HBOth_A   ,   sum_HBOth_P/sum_HBOth_A(10.2)      ,
                 '\n      HBSch_Pr',   sum_HBSchPr_P ,   sum_HBSchPr_A ,   sum_HBSchPr_P/sum_HBSchPr_A(10.2)  ,
                 '\n      HBSch_Sc',   sum_HBSchSc_P ,   sum_HBSchSc_A ,   sum_HBSchSc_P/sum_HBSchSc_A(10.2)  ,
                 '\n      HBC     ',   sum_HBC_P     ,   sum_HBC_A     ,   sum_HBC_P/sum_HBC_A(10.2)          ,
                 '\n      NHBW    ',   sum_NHBW_P    ,   sum_NHBW_A    ,   sum_NHBW_P/sum_NHBW_A(10.2)        ,
                 '\n      NHBNW   ',   sum_NHBNW_P   ,   sum_NHBNW_A   ,   sum_NHBNW_P/sum_NHBNW_A(10.2)      ,
                 '\n',
                 '\n    TotExt    ',   sum_TotExt_P  ,   sum_TotExt_A  ,   sum_TotExt_P/sum_TotExt_A(10.2)    ,
                 '\n      IX      ',   sum_IX_P      ,   sum_IX_A      ,   sum_IX_P/sum_IX_A(10.2)            ,
                 '\n      XI      ',   sum_XI_P      ,   sum_XI_A      ,   sum_XI_P/sum_XI_A(10.2)            ,
                 '\n      XX      ',   sum_XX_P      ,   sum_XX_A      ,   sum_XX_P/sum_XX_A(10.2)            ,
                 '\n',
                 '\n    TotTrk    ',   sum_TotTrk_P  ,   sum_TotTrk_A  ,   sum_TotTrk_P/sum_TotTrk_A(10.2)    ,
                 '\n      II_LT   ',   sum_II_LT_P   ,   sum_II_LT_A   ,   sum_II_LT_P/sum_II_LT_A(10.2)      ,
                 '\n      II_MD   ',   sum_II_MD_P   ,   sum_II_MD_A   ,   sum_II_MD_P/sum_II_MD_A(10.2)      ,
                 '\n      II_HV   ',   sum_II_HV_P   ,   sum_II_HV_A   ,   sum_II_HV_P/sum_II_HV_A(10.2)      ,
                 '\n      Ext_MD  ',   sum_Ext_MD_P  ,   sum_Ext_MD_A  ,   sum_Ext_MD_P/sum_Ext_MD_A(10.2)    ,
                 '\n      Ext_HV  ',   sum_Ext_HV_P  ,   sum_Ext_HV_A  ,   sum_Ext_HV_P/sum_Ext_HV_A(10.2)    ,
                 '\n',
                 '\n    Other summaries',
                 '\n      HBSch   ',   sum_HBSch_P   ,   sum_HBSch_A   ,   sum_HBSch_P/sum_HBSch_A(10.2)      ,
                 '\n      HBO     ',   sum_HBO_P     ,   sum_HBO_A     ,   sum_HBO_P/sum_HBO_A(10.2)          ,
                 '\n      NHB     ',   sum_NHB_P     ,   sum_NHB_A     ,   sum_NHB_P/sum_NHB_A(10.2)          ,
                 '\n      TTUNIQUE',   sum_TTUNIQUE_P,   sum_TTUNIQUE_A,   sum_TTUNIQUE_P/sum_TTUNIQUE_A(10.2),
                 '\n      HBOthnTT',   sum_HBOthnTT_P,   sum_HBOthnTT_A,   sum_HBOthnTT_P/sum_HBOthnTT_A(10.2),
                 '\n',
                 '\n      Tot_HBW ',   sum_Tot_HBW_P ,   sum_Tot_HBW_A ,   sum_Tot_HBW_P/sum_Tot_HBW_A(10.2)  ,
                 '\n      Tel_HBW ',   sum_Tel_HBW_P ,   sum_Tel_HBW_A ,   sum_Tel_HBW_P/sum_Tel_HBW_A(10.2)  ,
                 '\n      Tot_NHBW',   sum_Tot_NHBW_P,   sum_Tot_NHBW_A,   sum_Tot_NHBW_P/sum_Tot_NHBW_A(10.2),
                 '\n      Tel_NHBW',   sum_Tel_NHBW_P,   sum_Tel_NHBW_A,   sum_Tel_NHBW_P/sum_Tel_NHBW_A(10.2),
                 '\n',
                 '\n      TG_Per  ',   sum_TG_Per_P  ,   sum_TG_Per_A  ,   sum_TG_Per_P/sum_TG_Per_A(10.2)    ,
                 '\n      TG_IXXI ',   sum_TG_IXXI_P ,   sum_TG_IXXI_A ,   sum_TG_IXXI_P/sum_TG_IXXI_A(10.2)  ,
                 '\n      TG_Trk  ',   sum_TG_Trk_P  ,   sum_TG_Trk_A  ,   sum_TG_Trk_P/sum_TG_Trk_A(10.2)    ,
                 '\n',
                 '\n',
                 '\n  Intrazonal Summary',
                 '\n    Region    ',     '   Intrazonal',   '    Tot Trips',              '  % Intrazonal',
                 '\n      HBW     ',   intrazonal_HBW_RE,      total_HBW_RE,   pct_intrazonal_HBW_RE(13.1), '%',
                 '\n      HBO     ',   intrazonal_HBO_RE,      total_HBO_RE,   pct_intrazonal_HBO_RE(13.1), '%',
                 '\n      NHB     ',   intrazonal_NHB_RE,      total_NHB_RE,   pct_intrazonal_NHB_RE(13.1), '%',
                 '\n',                 
                 '\n    Box Elder ',     '   Intrazonal',   '    Tot Trips',              '  % Intrazonal',
                 '\n      HBW     ',   intrazonal_HBW_BE,      total_HBW_BE,   pct_intrazonal_HBW_BE(13.1), '%',
                 '\n      HBO     ',   intrazonal_HBO_BE,      total_HBO_BE,   pct_intrazonal_HBO_BE(13.1), '%',
                 '\n      NHB     ',   intrazonal_NHB_BE,      total_NHB_BE,   pct_intrazonal_NHB_BE(13.1), '%',
                 '\n',                 
                 '\n    Weber     ',     '   Intrazonal',   '    Tot Trips',              '  % Intrazonal',
                 '\n      HBW     ',   intrazonal_HBW_WE,      total_HBW_WE,   pct_intrazonal_HBW_WE(13.1), '%',
                 '\n      HBO     ',   intrazonal_HBO_WE,      total_HBO_WE,   pct_intrazonal_HBO_WE(13.1), '%',
                 '\n      NHB     ',   intrazonal_NHB_WE,      total_NHB_WE,   pct_intrazonal_NHB_WE(13.1), '%',
                 '\n',                 
                 '\n    Davis     ',     '   Intrazonal',   '    Tot Trips',              '  % Intrazonal',
                 '\n      HBW     ',   intrazonal_HBW_DA,      total_HBW_DA,   pct_intrazonal_HBW_DA(13.1), '%',
                 '\n      HBO     ',   intrazonal_HBO_DA,      total_HBO_DA,   pct_intrazonal_HBO_DA(13.1), '%',
                 '\n      NHB     ',   intrazonal_NHB_DA,      total_NHB_DA,   pct_intrazonal_NHB_DA(13.1), '%',
                 '\n',                 
                 '\n    Salt Lake ',     '   Intrazonal',   '    Tot Trips',              '  % Intrazonal',
                 '\n      HBW     ',   intrazonal_HBW_SL,      total_HBW_SL,   pct_intrazonal_HBW_SL(13.1), '%',
                 '\n      HBO     ',   intrazonal_HBO_SL,      total_HBO_SL,   pct_intrazonal_HBO_SL(13.1), '%',
                 '\n      NHB     ',   intrazonal_NHB_SL,      total_NHB_SL,   pct_intrazonal_NHB_SL(13.1), '%',
                 '\n',                 
                 '\n    Utah      ',     '   Intrazonal',   '    Tot Trips',              '  % Intrazonal',
                 '\n      HBW     ',   intrazonal_HBW_UT,      total_HBW_UT,   pct_intrazonal_HBW_UT(13.1), '%',
                 '\n      HBO     ',   intrazonal_HBO_UT,      total_HBO_UT,   pct_intrazonal_HBO_UT(13.1), '%',
                 '\n      NHB     ',   intrazonal_NHB_UT,      total_NHB_UT,   pct_intrazonal_NHB_UT(13.1), '%',
                 '\n',
                 '\n'
            
        endif  ;i=ZONES
        
    ENDRUN

;Cluster: bring together all distributed steps before continuing
BARRIER IDLIST='FinNet_Proc2' CheckReturnCode=T


;print timestamp
RUN PGM=MATRIX
    
    ZONES = 1
    
    SubScriptEndTime_FN = currenttime()
    SubScriptRunTime_FN = SubScriptEndTime_FN - @SubScriptStartTime_FN@
    
    PRINT FILE='@ScenarioDir@\_Log\_RunTime.txt',
        APPEND=T,
        LIST='\n',
             '\n        Prepare final loaded net and mtx  ', formatdatetime(SubScriptRunTime_FN, 40, 0, 'hhh:nn:ss')
    
ENDRUN



;Summarize PA_AllPurp Matrix into pa_final.dbf file (updated HBW and NHBW totals, adjsuted for telecommuting) =======================================================
RUN PGM=MATRIX MSG='Distribution: Summarize PA_AllPurp Matrix into pa_final.dbf file'
    
    FILEI ZDATI[1] = '@ScenarioDir@\2_TripGen\pa_initial.dbf'
    FILEI MATI[1]  ='@ScenarioDir@\3_Distribute\PA_AllPurp_GRAVITY.mtx'
    
    FILEO RECO[1] = '@ScenarioDir@\3_Distribute\pa_final.dbf',
        FORM=10.1,
        FIELDS= Z(6.0),
                CO_TAZID(10.0),
                CO_FIPS(6.0),
                SUBAREAID(6.0),
                AREATYPE(6.0),
                
               Total_P,      Total_A,
              TotPer_P,     TotPer_A,
              TotExt_P,     TotExt_A,
    
                 HBW_P,        HBW_A,
               HBShp_P,      HBShp_A,
               HBOth_P,      HBOth_A,
             HBSchPr_P,    HBSchPr_A,    ;primary education (k to 6)
             HBSchSc_P,    HBSchSc_A,    ;secondary education (7 to 12)
                NHBW_P,       NHBW_A,
               NHBNW_P,      NHBNW_A,
                 HBC_P,        HBC_A,
            TTUnique_P,   TTUnique_A,
           
                  IX_P,         IX_A,
                  XI_P,         XI_A
    
    ZONES   = @UsedZones@
    ZONEMSG = @ZoneMsgRate@
    
    ;arrays to store sums
    ARRAY mTOTAL_P    = @UsedZones@,
          mTOTAL_A    = @UsedZones@,
          mTOTPER_P   = @UsedZones@,
          mTOTPER_A   = @UsedZones@,
          mTOTEXT_P   = @UsedZones@,
          mTOTEXT_A   = @UsedZones@,
          mHBW_P      = @UsedZones@,
          mHBW_A      = @UsedZones@,
          mHBSHP_P    = @UsedZones@,
          mHBSHP_A    = @UsedZones@,
          mHBOTH_P    = @UsedZones@,
          mHBOTH_A    = @UsedZones@,
          mHBSCHPR_P  = @UsedZones@,
          mHBSCHPR_A  = @UsedZones@,
          mHBSCHSC_P  = @UsedZones@,
          mHBSCHSC_A  = @UsedZones@,
          mNHBW_P     = @UsedZones@,
          mNHBW_A     = @UsedZones@,
          mNHBNW_P    = @UsedZones@,
          mNHBNW_A    = @UsedZones@,
          mHBC_P      = @UsedZones@,
          mHBC_A      = @UsedZones@,
          mTTUNIQUE_P = @UsedZones@,
          mTTUNIQUE_A = @UsedZones@,
          mIX_P       = @UsedZones@,
          mIX_A       = @UsedZones@,
          mXI_P       = @UsedZones@,
          mXI_A       = @UsedZones@
    
    ; accumulate
    JLOOP J=1,ZONES
        
        ;productions
        mTOTAL_P[i]    = mTOTAL_P[i]     + mi.1.TOT[j]
        mTOTPER_P[i]   = mTOTPER_P[i]    + mi.1.HBW[j]      + 
                                           mi.1.HBShp[j]    + 
                                           mi.1.HBOth[j]    + 
                                           mi.1.HBSch_Pr[j] + 
                                           mi.1.HBSch_Sc[j] + 
                                           mi.1.NHBW[j]     + 
                                           mi.1.NHBNW[j]    + 
                                           mi.1.HBC[j]      + 
                                           mi.1.TTUNIQUE[j]
        mTOTEXT_P[i]   = mTOTEXT_P[i]    + mi.1.IX[j]       + 
                                           mi.1.XI[j]
        mHBW_P[i]      = mHBW_P[i]       + mi.1.HBW[j]
        mHBSHP_P[i]    = mHBSHP_P[i]     + mi.1.HBSHP[j]
        mHBOTH_P[i]    = mHBOTH_P[i]     + mi.1.HBOth
        mHBSCHPR_P[i]  = mHBSCHPR_P[i]   + mi.1.HBSch_Pr[j]
        mHBSCHSC_P[i]  = mHBSCHSC_P[i]   + mi.1.HBSch_Sc[j]
        mNHBW_P[i]     = mNHBW_P[i]      + mi.1.NHBW[j]
        mNHBNW_P[i]    = mNHBNW_P[i]     + mi.1.NHBNW[j]
        mHBC_P[i]      = mHBC_P[i]       + mi.1.HBC[j]
        mTTUNIQUE_P[i] = mTTUNIQUE_P[i]  + mi.1.TTUNIQUE[j]
        mIX_P[i]       = mIX_P[i]        + mi.1.IX[j]
        mXI_P[i]       = mXI_P[i]        + mi.1.XI[j]
        
        ;attractions
        mTOTAL_A[j]     = mTOTAL_A[j]    + mi.1.TOT[j]
        mTOTPER_A[j]    = mTOTPER_A[j]   + mi.1.HBW[j]      + 
                                           mi.1.HBShp[j]    + 
                                           mi.1.HBOth[j]    + 
                                           mi.1.HBSch_Pr[j] + 
                                           mi.1.HBSch_Sc[j] + 
                                           mi.1.NHBW[j]     + 
                                           mi.1.NHBNW[j]    + 
                                           mi.1.HBC[j]      + 
                                           mi.1.TTUNIQUE[j]
        mTOTEXT_A[j]    = mTOTEXT_A[j]   + mi.1.IX[j]       + 
                                           mi.1.XI[j]
        mHBW_A[j]       = mHBW_A[j]      + mi.1.HBW[j]
        mHBSHP_A[j]     = mHBSHP_A[j]    + mi.1.HBSHP[j]
        mHBOTH_A[j]     = mHBOTH_A[j]    + mi.1.HBOth
        mHBSCHPR_A[j]   = mHBSCHPR_A[j]  + mi.1.HBSch_Pr[j]
        mHBSCHSC_A[j]   = mHBSCHSC_A[j]  + mi.1.HBSch_Sc[j]
        mNHBW_A[j]      = mNHBW_A[j]     + mi.1.NHBW[j]
        mNHBNW_A[j]     = mNHBNW_A[j]    + mi.1.NHBNW[j]
        mHBC_A[j]       = mHBC_A[j]      + mi.1.HBC[j]
        mTTUNIQUE_A[j]  = mTTUNIQUE_A[j] + mi.1.TTUNIQUE[j]
        mIX_A[j]        = mIX_A[j]       + mi.1.IX[j]
        mXI_A[j]        = mXI_A[j]       + mi.1.XI[j]
        
    ENDJLOOP
    
    IF(I=ZONES)
        LOOP lp=1,ZONES
             RO.Z           = lp
             RO.CO_TAZID    = zi.1.CO_TAZID[lp]
             RO.CO_FIPS     = zi.1.CO_FIPS[lp]
             RO.SUBAREAID   = zi.1.SUBAREAID[lp]
             RO.AREATYPE    = zi.1.AREATYPE[lp]
             RO.TOTAL_P     = mTOTAL_P[lp]
             RO.TOTAL_A     = mTOTAL_A[lp]
             RO.TOTPER_P    = mTOTPER_P[lp]
             RO.TOTPER_A    = mTOTPER_A[lp]
             RO.TOTEXT_P    = mTOTEXT_P[lp]
             RO.TOTEXT_A    = mTOTEXT_A[lp]
             RO.HBW_P       = mHBW_P[lp]
             RO.HBW_A       = mHBW_A[lp]
             RO.HBSHP_P     = mHBSHP_P[lp]
             RO.HBSHP_A     = mHBSHP_A[lp]
             RO.HBOTH_P     = mHBOTH_P[lp]
             RO.HBOTH_A     = mHBOTH_A[lp]
             RO.HBSCHPR_P   = mHBSCHPR_P[lp]
             RO.HBSCHPR_A   = mHBSCHPR_A[lp]
             RO.HBSCHSC_P   = mHBSCHSC_P[lp]
             RO.HBSCHSC_A   = mHBSCHSC_A[lp]
             RO.NHBW_P      = mNHBW_P[lp]
             RO.NHBW_A      = mNHBW_A[lp]
             RO.NHBNW_P     = mNHBNW_P[lp]
             RO.NHBNW_A     = mNHBNW_A[lp]
             RO.HBC_P       = mHBC_P[lp]
             RO.HBC_A       = mHBC_A[lp]
             RO.TTUNIQUE_P  = mTTUNIQUE_P[lp]
             RO.TTUNIQUE_A  = mTTUNIQUE_A[lp]
             RO.IX_P        = mIX_P[lp]
             RO.IX_A        = mIX_A[lp]
             RO.XI_P        = mXI_P[lp]
             RO.XI_A        = mXI_A[lp]
            
            WRITE RECO=1
            
        ENDLOOP
    ENDIF

ENDRUN


RUN PGM=MATRIX MSG='0: Run Python Script to Convert pa_final.dbf to pa_final.csv'

    ZONES = 1
    
    ;create control input file for this Python script
    PRINT FILE = '@ScenarioDir@\_Log\py_Variables - dbf_to_csv.txt',
        LIST='#Python input file variables and paths',
            '\nModelDir_Py    = @ModelDir_Py@',
            '\nScenarioDir_Py = @ScenarioDir_Py@',
            '\nFileName       = 3_Distribute//pa_final',
            '\n',
            '\n'
ENDRUN

;Python script: create json for transit routes
;  note using single asterix minimizes the command window when executed, double asterix executes the command window non-minimized
;  note: the 1>&2 echos the python window output to the one started by Cube
**"@ModelDir@\2_ModelScripts\_Python\py-tdm-env\python.exe" "@ModelDir@\2_ModelScripts\_Python\_dbf_to_csv.py" 1>&2


;handle python script errors
if (ReturnCode<>0)
    
    PROMPT QUESTION='Python failed to run correctly',
        ANSWER="Please check the py log file in '@ScenarioDir@\_Log' for error messages."
    
    GOTO :ONERROR
    
    ABORT
    
endif  ;ReturnCode<>0




;calculate Daily PA skims by trip purpose from period OD skims =============================================================================

;get start time
SubScriptStartTime_TD = currenttime()



LOOP _LOS=1, 2
    
    ;output filename tag to differentiate generalized cost, time or distance output matrices
    if (_LOS=1)  skim_type = 'Time'
    if (_LOS=2)  skim_type = 'Dist'
    
    ;prefix to identify which skim type or set of matrices in input skim matrix files
    if (_LOS=1)  matrix_prefix = 'time'
    if (_LOS=2)  matrix_prefix = 'distance'
    
    
    
    RUN PGM=MATRIX  MSG='Distribution: Feedback Loop @n@: Create Daily Average Skim - @skim_type@'
        
        FILEI MATI[1] = '@ScenarioDir@\3_Distribute\skm_AM.mtx'
        FILEI MATI[2] = '@ScenarioDir@\3_Distribute\skm_MD.mtx'
        FILEI MATI[3] = '@ScenarioDir@\3_Distribute\skm_PM.mtx'
        FILEI MATI[4] = '@ScenarioDir@\3_Distribute\skm_EV.mtx'
        
        
        FILEO MATO[1] = '@ScenarioDir@\3_Distribute\skm_DY_@skim_type@.mtx',
                mo=510, 520-522, 530-532, 540, 550, 560, 570, 580, 590, 500,
                name=HBW   ,
                     HBO   ,
                     HBShp ,
                     HBOth ,
                     NHB   ,
                     NHBW  ,
                     NHBNW ,
                     HBS   ,
                     HBC   ,
                     Rec   ,
                     LT    ,
                     MD    ,
                     HV    ,
                     Ext   
        
        
        ;Cluster: distribute intrastep processing
        DistributeIntrastep MaxProcesses=@CoresAvailable@
        
        
        
        ZONES   = @Usedzones@
        ZONEMSG = 10
        
        
        
        ;print status to task monitor window
        PrintProgress = INT((i-FIRSTZONE) / (LASTZONE-FIRSTZONE) * 100)
        PrintProgInc = 1
        
        if (i=FIRSTZONE)
            PRINT PRINTO=0, LIST='Processing: ', PrintProgress(5.0), '%'
            CheckProgress = PrintProgInc
        elseif (PrintProgress=CheckProgress)
            PRINT PRINTO=0, LIST='Processing: ', PrintProgress(5.0), '%'
            CheckProgress = CheckProgress + PrintProgInc
        endif
        
        
        
        ;read in calculated diurnal factors from file
        if (i=FIRSTZONE)
            
            ;read in calculate diurnal factors block file
            READ FILE = '@ScenarioDir@\0_InputProcessing\_TimeOfDayFactors.txt'
            
        endif  ;i=FIRSTZONE
        
        
        
        ;read in skim tables ---------------------------------------------------------------------------------
        ;  note: AP direction is the transpose of PA direction
        
        ;AM
        mw[101] = mi.1.@matrix_prefix@_Auto_WRK
        mw[102] = mi.1.@matrix_prefix@_Auto_Per
        mw[103] = mi.1.@matrix_prefix@_Auto_Ext
        mw[104] = mi.1.@matrix_prefix@_Truck_LT
        mw[105] = mi.1.@matrix_prefix@_Truck_MD
        mw[106] = mi.1.@matrix_prefix@_Truck_HV
        
        mw[151] = mi.1.@matrix_prefix@_Auto_WRK.T
        mw[152] = mi.1.@matrix_prefix@_Auto_Per.T
        mw[153] = mi.1.@matrix_prefix@_Auto_Ext.T
        mw[154] = mi.1.@matrix_prefix@_Truck_LT.T
        mw[155] = mi.1.@matrix_prefix@_Truck_MD.T
        mw[156] = mi.1.@matrix_prefix@_Truck_HV.T
        
        ;MD
        mw[201] = mi.2.@matrix_prefix@_Auto_WRK
        mw[202] = mi.2.@matrix_prefix@_Auto_Per
        mw[203] = mi.2.@matrix_prefix@_Auto_Ext
        mw[204] = mi.2.@matrix_prefix@_Truck_LT
        mw[205] = mi.2.@matrix_prefix@_Truck_MD
        mw[206] = mi.2.@matrix_prefix@_Truck_HV
        
        mw[251] = mi.2.@matrix_prefix@_Auto_WRK.T
        mw[252] = mi.2.@matrix_prefix@_Auto_Per.T
        mw[253] = mi.2.@matrix_prefix@_Auto_Ext.T
        mw[254] = mi.2.@matrix_prefix@_Truck_LT.T
        mw[255] = mi.2.@matrix_prefix@_Truck_MD.T
        mw[256] = mi.2.@matrix_prefix@_Truck_HV.T
        
        ;PM
        mw[301] = mi.3.@matrix_prefix@_Auto_WRK
        mw[302] = mi.3.@matrix_prefix@_Auto_Per
        mw[303] = mi.3.@matrix_prefix@_Auto_Ext
        mw[304] = mi.3.@matrix_prefix@_Truck_LT
        mw[305] = mi.3.@matrix_prefix@_Truck_MD
        mw[306] = mi.3.@matrix_prefix@_Truck_HV
        
        mw[351] = mi.3.@matrix_prefix@_Auto_WRK.T
        mw[352] = mi.3.@matrix_prefix@_Auto_Per.T
        mw[353] = mi.3.@matrix_prefix@_Auto_Ext.T
        mw[354] = mi.3.@matrix_prefix@_Truck_LT.T
        mw[355] = mi.3.@matrix_prefix@_Truck_MD.T
        mw[356] = mi.3.@matrix_prefix@_Truck_HV.T
        
        ;EV
        mw[401] = mi.4.@matrix_prefix@_Auto_WRK
        mw[402] = mi.4.@matrix_prefix@_Auto_Per
        mw[403] = mi.4.@matrix_prefix@_Auto_Ext
        mw[404] = mi.4.@matrix_prefix@_Truck_LT
        mw[405] = mi.4.@matrix_prefix@_Truck_MD
        mw[406] = mi.4.@matrix_prefix@_Truck_HV
        
        mw[451] = mi.4.@matrix_prefix@_Auto_WRK.T
        mw[452] = mi.4.@matrix_prefix@_Auto_Per.T
        mw[453] = mi.4.@matrix_prefix@_Auto_Ext.T
        mw[454] = mi.4.@matrix_prefix@_Truck_LT.T
        mw[455] = mi.4.@matrix_prefix@_Truck_MD.T
        mw[456] = mi.4.@matrix_prefix@_Truck_HV.T
        
        
        
        ;calculate weighted average daily skim ---------------------------------------------------------------
        ;loop through columns to identify movement (II, IX, XI or XX)
        JLOOP
            
            ;II
            if (!(i=@externalzones@) & !(j=@externalzones@))
                
                ;work trip skim
                mw[510] = mw[101] * Pct_AM_HBW * PA_AM_HBW  +  mw[151] * Pct_AM_HBW * (1 - PA_AM_HBW)  +
                          mw[201] * Pct_MD_HBW * PA_MD_HBW  +  mw[251] * Pct_MD_HBW * (1 - PA_MD_HBW)  +
                          mw[301] * Pct_PM_HBW * PA_PM_HBW  +  mw[351] * Pct_PM_HBW * (1 - PA_PM_HBW)  +
                          mw[401] * Pct_EV_HBW * PA_EV_HBW  +  mw[451] * Pct_EV_HBW * (1 - PA_EV_HBW)  
                
                
                ;personal trip skim
                mw[520] = mw[102] * Pct_AM_HBO * PA_AM_HBO      +  mw[152] * Pct_AM_HBO   * (1 - PA_AM_HBO)   +
                          mw[202] * Pct_MD_HBO * PA_MD_HBO      +  mw[252] * Pct_MD_HBO   * (1 - PA_MD_HBO)   +
                          mw[302] * Pct_PM_HBO * PA_PM_HBO      +  mw[352] * Pct_PM_HBO   * (1 - PA_PM_HBO)   +
                          mw[402] * Pct_EV_HBO * PA_EV_HBO      +  mw[452] * Pct_EV_HBO   * (1 - PA_EV_HBO)    
                
                mw[521] = mw[102] * Pct_AM_HBShp * PA_AM_HBShp  +  mw[152] * Pct_AM_HBShp * (1 - PA_AM_HBShp) +
                          mw[202] * Pct_MD_HBShp * PA_MD_HBShp  +  mw[252] * Pct_MD_HBShp * (1 - PA_MD_HBShp) +
                          mw[302] * Pct_PM_HBShp * PA_PM_HBShp  +  mw[352] * Pct_PM_HBShp * (1 - PA_PM_HBShp) +
                          mw[402] * Pct_EV_HBShp * PA_EV_HBShp  +  mw[452] * Pct_EV_HBShp * (1 - PA_EV_HBShp)  
                
                mw[522] = mw[102] * Pct_AM_HBOth * PA_AM_HBOth  +  mw[152] * Pct_AM_HBOth * (1 - PA_AM_HBOth) +
                          mw[202] * Pct_MD_HBOth * PA_MD_HBOth  +  mw[252] * Pct_MD_HBOth * (1 - PA_MD_HBOth) +
                          mw[302] * Pct_PM_HBOth * PA_PM_HBOth  +  mw[352] * Pct_PM_HBOth * (1 - PA_PM_HBOth) +
                          mw[402] * Pct_EV_HBOth * PA_EV_HBOth  +  mw[452] * Pct_EV_HBOth * (1 - PA_EV_HBOth)  
                
                mw[530] = mw[102] * Pct_AM_NHB * PA_AM_NHB      +  mw[152] * Pct_AM_NHB   * (1 - PA_AM_NHB)   +
                          mw[202] * Pct_MD_NHB * PA_MD_NHB      +  mw[252] * Pct_MD_NHB   * (1 - PA_MD_NHB)   +
                          mw[302] * Pct_PM_NHB * PA_PM_NHB      +  mw[352] * Pct_PM_NHB   * (1 - PA_PM_NHB)   +
                          mw[402] * Pct_EV_NHB * PA_EV_NHB      +  mw[452] * Pct_EV_NHB   * (1 - PA_EV_NHB)    
                
                mw[531] = mw[102] * Pct_AM_NHBW * PA_AM_NHBW    +  mw[152] * Pct_AM_NHBW  * (1 - PA_AM_NHBW)  +
                          mw[202] * Pct_MD_NHBW * PA_MD_NHBW    +  mw[252] * Pct_MD_NHBW  * (1 - PA_MD_NHBW)  +
                          mw[302] * Pct_PM_NHBW * PA_PM_NHBW    +  mw[352] * Pct_PM_NHBW  * (1 - PA_PM_NHBW)  +
                          mw[402] * Pct_EV_NHBW * PA_EV_NHBW    +  mw[452] * Pct_EV_NHBW  * (1 - PA_EV_NHBW)   
                
                mw[532] = mw[102] * Pct_AM_NHBNW * PA_AM_NHBNW  +  mw[152] * Pct_AM_NHBNW * (1 - PA_AM_NHBNW) +
                          mw[202] * Pct_MD_NHBNW * PA_MD_NHBNW  +  mw[252] * Pct_MD_NHBNW * (1 - PA_MD_NHBNW) +
                          mw[302] * Pct_PM_NHBNW * PA_PM_NHBNW  +  mw[352] * Pct_PM_NHBNW * (1 - PA_PM_NHBNW) +
                          mw[402] * Pct_EV_NHBNW * PA_EV_NHBNW  +  mw[452] * Pct_EV_NHBNW * (1 - PA_EV_NHBNW)  
                
                mw[540] = mw[102] * Pct_AM_HBS * PA_AM_HBS      +  mw[152] * Pct_AM_HBS   * (1 - PA_AM_HBS)   +
                          mw[202] * Pct_MD_HBS * PA_MD_HBS      +  mw[252] * Pct_MD_HBS   * (1 - PA_MD_HBS)   +
                          mw[302] * Pct_PM_HBS * PA_PM_HBS      +  mw[352] * Pct_PM_HBS   * (1 - PA_PM_HBS)   +
                          mw[402] * Pct_EV_HBS * PA_EV_HBS      +  mw[452] * Pct_EV_HBS   * (1 - PA_EV_HBS)    
                
                mw[550] = mw[102] * Pct_AM_HBC * PA_AM_HBC      +  mw[152] * Pct_AM_HBC   * (1 - PA_AM_HBC)   +
                          mw[202] * Pct_MD_HBC * PA_MD_HBC      +  mw[252] * Pct_MD_HBC   * (1 - PA_MD_HBC)   +
                          mw[302] * Pct_PM_HBC * PA_PM_HBC      +  mw[352] * Pct_PM_HBC   * (1 - PA_PM_HBC)   +
                          mw[402] * Pct_EV_HBC * PA_EV_HBC      +  mw[452] * Pct_EV_HBC   * (1 - PA_EV_HBC)    
                
                mw[560] = mw[102] * Pct_AM_Rec * PA_AM_Rec      +  mw[152] * Pct_AM_Rec   * (1 - PA_AM_Rec)   +
                          mw[202] * Pct_MD_Rec * PA_MD_Rec      +  mw[252] * Pct_MD_Rec   * (1 - PA_MD_Rec)   +
                          mw[302] * Pct_PM_Rec * PA_PM_Rec      +  mw[352] * Pct_PM_Rec   * (1 - PA_PM_Rec)   +
                          mw[402] * Pct_EV_Rec * PA_EV_Rec      +  mw[452] * Pct_EV_Rec   * (1 - PA_EV_Rec)    
                
                
                ;light truck skim
                mw[570] = mw[104] * Pct_AM_LT * PA_AM_LT  +  mw[154] * Pct_AM_LT * (1 - PA_AM_LT)  +
                          mw[204] * Pct_MD_LT * PA_MD_LT  +  mw[254] * Pct_MD_LT * (1 - PA_MD_LT)  +
                          mw[304] * Pct_PM_LT * PA_PM_LT  +  mw[354] * Pct_PM_LT * (1 - PA_PM_LT)  +
                          mw[404] * Pct_EV_LT * PA_EV_LT  +  mw[454] * Pct_EV_LT * (1 - PA_EV_LT)   
                
                
                ;medium truck skim
                mw[580] = mw[105] * Pct_AM_MD * PA_AM_MD  +  mw[155] * Pct_AM_MD * (1 - PA_AM_MD)  +
                          mw[205] * Pct_MD_MD * PA_MD_MD  +  mw[255] * Pct_MD_MD * (1 - PA_MD_MD)  +
                          mw[305] * Pct_PM_MD * PA_PM_MD  +  mw[355] * Pct_PM_MD * (1 - PA_PM_MD)  +
                          mw[405] * Pct_EV_MD * PA_EV_MD  +  mw[455] * Pct_EV_MD * (1 - PA_EV_MD)   
                
                
                ;heavy truck skim
                mw[590] = mw[106] * Pct_AM_HV * PA_AM_HV  +  mw[156] * Pct_AM_HV * (1 - PA_AM_HV)  +
                          mw[206] * Pct_MD_HV * PA_MD_HV  +  mw[256] * Pct_MD_HV * (1 - PA_MD_HV)  +
                          mw[306] * Pct_PM_HV * PA_PM_HV  +  mw[356] * Pct_PM_HV * (1 - PA_PM_HV)  +
                          mw[406] * Pct_EV_HV * PA_EV_HV  +  mw[456] * Pct_EV_HV * (1 - PA_EV_HV)   
                
                
            ;IX
            elseif (!(i=@externalzones@) & j=@externalzones@)
                
                ;external skim
                mw[500] = mw[103] * Pct_AM_IX * PA_AM_IX  +  mw[153] * Pct_AM_IX * (1 - PA_AM_IX) +
                          mw[203] * Pct_MD_IX * PA_MD_IX  +  mw[253] * Pct_MD_IX * (1 - PA_MD_IX) +
                          mw[303] * Pct_PM_IX * PA_PM_IX  +  mw[353] * Pct_PM_IX * (1 - PA_PM_IX) +
                          mw[403] * Pct_EV_IX * PA_EV_IX  +  mw[453] * Pct_EV_IX * (1 - PA_EV_IX)
                
                
                ;work trip skim
                mw[510] = mw[101] * Pct_AM_IX_HBW * PA_AM_IX_HBW  +  mw[151] * Pct_AM_IX_HBW * (1 - PA_AM_IX_HBW)  +
                          mw[201] * Pct_MD_IX_HBW * PA_MD_IX_HBW  +  mw[251] * Pct_MD_IX_HBW * (1 - PA_MD_IX_HBW)  +
                          mw[301] * Pct_PM_IX_HBW * PA_PM_IX_HBW  +  mw[351] * Pct_PM_IX_HBW * (1 - PA_PM_IX_HBW)  +
                          mw[401] * Pct_EV_IX_HBW * PA_EV_IX_HBW  +  mw[451] * Pct_EV_IX_HBW * (1 - PA_EV_IX_HBW)  
                
                
                ;personal trip skim
                mw[520] = mw[102] * Pct_AM_IX_HBO * PA_AM_IX_HBO  +  mw[152] * Pct_AM_IX_HBO * (1 - PA_AM_IX_HBO)  +
                          mw[202] * Pct_MD_IX_HBO * PA_MD_IX_HBO  +  mw[252] * Pct_MD_IX_HBO * (1 - PA_MD_IX_HBO)  +
                          mw[302] * Pct_PM_IX_HBO * PA_PM_IX_HBO  +  mw[352] * Pct_PM_IX_HBO * (1 - PA_PM_IX_HBO)  +
                          mw[402] * Pct_EV_IX_HBO * PA_EV_IX_HBO  +  mw[452] * Pct_EV_IX_HBO * (1 - PA_EV_IX_HBO)   
                
                mw[530] = mw[102] * Pct_AM_IX_NHB * PA_AM_IX_NHB  +  mw[152] * Pct_AM_IX_NHB * (1 - PA_AM_IX_NHB)  +
                          mw[202] * Pct_MD_IX_NHB * PA_MD_IX_NHB  +  mw[252] * Pct_MD_IX_NHB * (1 - PA_MD_IX_NHB)  +
                          mw[302] * Pct_PM_IX_NHB * PA_PM_IX_NHB  +  mw[352] * Pct_PM_IX_NHB * (1 - PA_PM_IX_NHB)  +
                          mw[402] * Pct_EV_IX_NHB * PA_EV_IX_NHB  +  mw[452] * Pct_EV_IX_NHB * (1 - PA_EV_IX_NHB)   
                
                mw[540] = mw[102] * Pct_AM_IX_HBS * PA_AM_IX_HBS  +  mw[152] * Pct_AM_IX_HBS * (1 - PA_AM_IX_HBS)  +
                          mw[202] * Pct_MD_IX_HBS * PA_MD_IX_HBS  +  mw[252] * Pct_MD_IX_HBS * (1 - PA_MD_IX_HBS)  +
                          mw[302] * Pct_PM_IX_HBS * PA_PM_IX_HBS  +  mw[352] * Pct_PM_IX_HBS * (1 - PA_PM_IX_HBS)  +
                          mw[402] * Pct_EV_IX_HBS * PA_EV_IX_HBS  +  mw[452] * Pct_EV_IX_HBS * (1 - PA_EV_IX_HBS)   
                
                mw[550] = mw[102] * Pct_AM_IX_HBC * PA_AM_IX_HBC  +  mw[152] * Pct_AM_IX_HBC * (1 - PA_AM_IX_HBC)  +
                          mw[202] * Pct_MD_IX_HBC * PA_MD_IX_HBC  +  mw[252] * Pct_MD_IX_HBC * (1 - PA_MD_IX_HBC)  +
                          mw[302] * Pct_PM_IX_HBC * PA_PM_IX_HBC  +  mw[352] * Pct_PM_IX_HBC * (1 - PA_PM_IX_HBC)  +
                          mw[402] * Pct_EV_IX_HBC * PA_EV_IX_HBC  +  mw[452] * Pct_EV_IX_HBC * (1 - PA_EV_IX_HBC)   
                
                mw[560] = mw[102] * Pct_AM_IX_Rec * PA_AM_IX_Rec  +  mw[152] * Pct_AM_IX_Rec * (1 - PA_AM_IX_Rec)  +
                          mw[202] * Pct_MD_IX_Rec * PA_MD_IX_Rec  +  mw[252] * Pct_MD_IX_Rec * (1 - PA_MD_IX_Rec)  +
                          mw[302] * Pct_PM_IX_Rec * PA_PM_IX_Rec  +  mw[352] * Pct_PM_IX_Rec * (1 - PA_PM_IX_Rec)  +
                          mw[402] * Pct_EV_IX_Rec * PA_EV_IX_Rec  +  mw[452] * Pct_EV_IX_Rec * (1 - PA_EV_IX_Rec)   
                
                
                ;light truck skim
                mw[570] = mw[104] * Pct_AM_IX_LT * PA_AM_IX_LT  +  mw[154] * Pct_AM_IX_LT * (1 - PA_AM_IX_LT)  +
                          mw[204] * Pct_MD_IX_LT * PA_MD_IX_LT  +  mw[254] * Pct_MD_IX_LT * (1 - PA_MD_IX_LT)  +
                          mw[304] * Pct_PM_IX_LT * PA_PM_IX_LT  +  mw[354] * Pct_PM_IX_LT * (1 - PA_PM_IX_LT)  +
                          mw[404] * Pct_EV_IX_LT * PA_EV_IX_LT  +  mw[454] * Pct_EV_IX_LT * (1 - PA_EV_IX_LT)   
                
                
                ;medium truck skim
                mw[580] = mw[105] * Pct_AM_IX_MD * PA_AM_IX_MD  +  mw[155] * Pct_AM_IX_MD * (1 - PA_AM_IX_MD)  +
                          mw[205] * Pct_MD_IX_MD * PA_MD_IX_MD  +  mw[255] * Pct_MD_IX_MD * (1 - PA_MD_IX_MD)  +
                          mw[305] * Pct_PM_IX_MD * PA_PM_IX_MD  +  mw[355] * Pct_PM_IX_MD * (1 - PA_PM_IX_MD)  +
                          mw[405] * Pct_EV_IX_MD * PA_EV_IX_MD  +  mw[455] * Pct_EV_IX_MD * (1 - PA_EV_IX_MD)   
                
                
                ;heavy truck skim
                mw[590] = mw[106] * Pct_AM_IX_HV * PA_AM_IX_HV  +  mw[156] * Pct_AM_IX_HV * (1 - PA_AM_IX_HV)  +
                          mw[206] * Pct_MD_IX_HV * PA_MD_IX_HV  +  mw[256] * Pct_MD_IX_HV * (1 - PA_MD_IX_HV)  +
                          mw[306] * Pct_PM_IX_HV * PA_PM_IX_HV  +  mw[356] * Pct_PM_IX_HV * (1 - PA_PM_IX_HV)  +
                          mw[406] * Pct_EV_IX_HV * PA_EV_IX_HV  +  mw[456] * Pct_EV_IX_HV * (1 - PA_EV_IX_HV)   
                
                
            ;XI
            elseif (i=@externalzones@ & !(j=@externalzones@))
                
                ;external skim
                mw[500] = mw[103] * Pct_AM_XI * PA_AM_XI  +  mw[153] * Pct_AM_XI * (1 - PA_AM_XI) +
                          mw[203] * Pct_MD_XI * PA_MD_XI  +  mw[253] * Pct_MD_XI * (1 - PA_MD_XI) +
                          mw[303] * Pct_PM_XI * PA_PM_XI  +  mw[353] * Pct_PM_XI * (1 - PA_PM_XI) +
                          mw[403] * Pct_EV_XI * PA_EV_XI  +  mw[453] * Pct_EV_XI * (1 - PA_EV_XI)
                
                
                ;work trip skim
                mw[510] = mw[101] * Pct_AM_XI_HBW * PA_AM_XI_HBW  +  mw[151] * Pct_AM_XI_HBW * (1 - PA_AM_XI_HBW)  +
                          mw[201] * Pct_MD_XI_HBW * PA_MD_XI_HBW  +  mw[251] * Pct_MD_XI_HBW * (1 - PA_MD_XI_HBW)  +
                          mw[301] * Pct_PM_XI_HBW * PA_PM_XI_HBW  +  mw[351] * Pct_PM_XI_HBW * (1 - PA_PM_XI_HBW)  +
                          mw[401] * Pct_EV_XI_HBW * PA_EV_XI_HBW  +  mw[451] * Pct_EV_XI_HBW * (1 - PA_EV_XI_HBW)  
                
                
                ;personal trip skim
                mw[520] = mw[102] * Pct_AM_XI_HBO * PA_AM_XI_HBO  +  mw[152] * Pct_AM_XI_HBO * (1 - PA_AM_XI_HBO)  +
                          mw[202] * Pct_MD_XI_HBO * PA_MD_XI_HBO  +  mw[252] * Pct_MD_XI_HBO * (1 - PA_MD_XI_HBO)  +
                          mw[302] * Pct_PM_XI_HBO * PA_PM_XI_HBO  +  mw[352] * Pct_PM_XI_HBO * (1 - PA_PM_XI_HBO)  +
                          mw[402] * Pct_EV_XI_HBO * PA_EV_XI_HBO  +  mw[452] * Pct_EV_XI_HBO * (1 - PA_EV_XI_HBO)   
                
                mw[530] = mw[102] * Pct_AM_XI_NHB * PA_AM_XI_NHB  +  mw[152] * Pct_AM_XI_NHB * (1 - PA_AM_XI_NHB)  +
                          mw[202] * Pct_MD_XI_NHB * PA_MD_XI_NHB  +  mw[252] * Pct_MD_XI_NHB * (1 - PA_MD_XI_NHB)  +
                          mw[302] * Pct_PM_XI_NHB * PA_PM_XI_NHB  +  mw[352] * Pct_PM_XI_NHB * (1 - PA_PM_XI_NHB)  +
                          mw[402] * Pct_EV_XI_NHB * PA_EV_XI_NHB  +  mw[452] * Pct_EV_XI_NHB * (1 - PA_EV_XI_NHB)   
                
                mw[540] = mw[102] * Pct_AM_XI_HBS * PA_AM_XI_HBS  +  mw[152] * Pct_AM_XI_HBS * (1 - PA_AM_XI_HBS)  +
                          mw[202] * Pct_MD_XI_HBS * PA_MD_XI_HBS  +  mw[252] * Pct_MD_XI_HBS * (1 - PA_MD_XI_HBS)  +
                          mw[302] * Pct_PM_XI_HBS * PA_PM_XI_HBS  +  mw[352] * Pct_PM_XI_HBS * (1 - PA_PM_XI_HBS)  +
                          mw[402] * Pct_EV_XI_HBS * PA_EV_XI_HBS  +  mw[452] * Pct_EV_XI_HBS * (1 - PA_EV_XI_HBS)   
                
                mw[550] = mw[102] * Pct_AM_XI_HBC * PA_AM_XI_HBC  +  mw[152] * Pct_AM_XI_HBC * (1 - PA_AM_XI_HBC)  +
                          mw[202] * Pct_MD_XI_HBC * PA_MD_XI_HBC  +  mw[252] * Pct_MD_XI_HBC * (1 - PA_MD_XI_HBC)  +
                          mw[302] * Pct_PM_XI_HBC * PA_PM_XI_HBC  +  mw[352] * Pct_PM_XI_HBC * (1 - PA_PM_XI_HBC)  +
                          mw[402] * Pct_EV_XI_HBC * PA_EV_XI_HBC  +  mw[452] * Pct_EV_XI_HBC * (1 - PA_EV_XI_HBC)   
                
                mw[560] = mw[102] * Pct_AM_XI_Rec * PA_AM_XI_Rec  +  mw[152] * Pct_AM_XI_Rec * (1 - PA_AM_XI_Rec)  +
                          mw[202] * Pct_MD_XI_Rec * PA_MD_XI_Rec  +  mw[252] * Pct_MD_XI_Rec * (1 - PA_MD_XI_Rec)  +
                          mw[302] * Pct_PM_XI_Rec * PA_PM_XI_Rec  +  mw[352] * Pct_PM_XI_Rec * (1 - PA_PM_XI_Rec)  +
                          mw[402] * Pct_EV_XI_Rec * PA_EV_XI_Rec  +  mw[452] * Pct_EV_XI_Rec * (1 - PA_EV_XI_Rec)   
                
                
                ;light truck skim
                mw[570] = mw[104] * Pct_AM_XI_LT * PA_AM_XI_LT  +  mw[154] * Pct_AM_XI_LT * (1 - PA_AM_XI_LT)  +
                          mw[204] * Pct_MD_XI_LT * PA_MD_XI_LT  +  mw[254] * Pct_MD_XI_LT * (1 - PA_MD_XI_LT)  +
                          mw[304] * Pct_PM_XI_LT * PA_PM_XI_LT  +  mw[354] * Pct_PM_XI_LT * (1 - PA_PM_XI_LT)  +
                          mw[404] * Pct_EV_XI_LT * PA_EV_XI_LT  +  mw[454] * Pct_EV_XI_LT * (1 - PA_EV_XI_LT)   
                
                
                ;medium truck skim
                mw[580] = mw[105] * Pct_AM_XI_MD * PA_AM_XI_MD  +  mw[155] * Pct_AM_XI_MD * (1 - PA_AM_XI_MD)  +
                          mw[205] * Pct_MD_XI_MD * PA_MD_XI_MD  +  mw[255] * Pct_MD_XI_MD * (1 - PA_MD_XI_MD)  +
                          mw[305] * Pct_PM_XI_MD * PA_PM_XI_MD  +  mw[355] * Pct_PM_XI_MD * (1 - PA_PM_XI_MD)  +
                          mw[405] * Pct_EV_XI_MD * PA_EV_XI_MD  +  mw[455] * Pct_EV_XI_MD * (1 - PA_EV_XI_MD)   
                
                
                ;heavy truck skim
                mw[590] = mw[106] * Pct_AM_XI_HV * PA_AM_XI_HV  +  mw[156] * Pct_AM_XI_HV * (1 - PA_AM_XI_HV)  +
                          mw[206] * Pct_MD_XI_HV * PA_MD_XI_HV  +  mw[256] * Pct_MD_XI_HV * (1 - PA_MD_XI_HV)  +
                          mw[306] * Pct_PM_XI_HV * PA_PM_XI_HV  +  mw[356] * Pct_PM_XI_HV * (1 - PA_PM_XI_HV)  +
                          mw[406] * Pct_EV_XI_HV * PA_EV_XI_HV  +  mw[456] * Pct_EV_XI_HV * (1 - PA_EV_XI_HV)   
                
                
            ;XX
            elseif (i=@externalzones@ & j=@externalzones@)
                
                ;external skim
                mw[500] = mw[103] * Pct_AM_XX * PA_AM_XX  +  mw[153] * Pct_AM_XX * (1 - PA_AM_XX) +
                          mw[203] * Pct_MD_XX * PA_MD_XX  +  mw[253] * Pct_MD_XX * (1 - PA_MD_XX) + 
                          mw[303] * Pct_PM_XX * PA_PM_XX  +  mw[353] * Pct_PM_XX * (1 - PA_PM_XX) +
                          mw[403] * Pct_EV_XX * PA_EV_XX  +  mw[453] * Pct_EV_XX * (1 - PA_EV_XX)
                
                
                ;work trip skim
                mw[510] = mw[101] * Pct_AM_XX_HBW * PA_AM_XX_HBW  +  mw[151] * Pct_AM_XX_HBW * (1 - PA_AM_XX_HBW)  +
                          mw[201] * Pct_MD_XX_HBW * PA_MD_XX_HBW  +  mw[251] * Pct_MD_XX_HBW * (1 - PA_MD_XX_HBW)  +
                          mw[301] * Pct_PM_XX_HBW * PA_PM_XX_HBW  +  mw[351] * Pct_PM_XX_HBW * (1 - PA_PM_XX_HBW)  +
                          mw[401] * Pct_EV_XX_HBW * PA_EV_XX_HBW  +  mw[451] * Pct_EV_XX_HBW * (1 - PA_EV_XX_HBW)  
                
                
                ;personal trip skim
                mw[520] = mw[102] * Pct_AM_XX_HBO * PA_AM_XX_HBO  +  mw[152] * Pct_AM_XX_HBO * (1 - PA_AM_XX_HBO)  +
                          mw[202] * Pct_MD_XX_HBO * PA_MD_XX_HBO  +  mw[252] * Pct_MD_XX_HBO * (1 - PA_MD_XX_HBO)  +
                          mw[302] * Pct_PM_XX_HBO * PA_PM_XX_HBO  +  mw[352] * Pct_PM_XX_HBO * (1 - PA_PM_XX_HBO)  +
                          mw[402] * Pct_EV_XX_HBO * PA_EV_XX_HBO  +  mw[452] * Pct_EV_XX_HBO * (1 - PA_EV_XX_HBO)   
                
                mw[530] = mw[102] * Pct_AM_XX_NHB * PA_AM_XX_NHB  +  mw[152] * Pct_AM_XX_NHB * (1 - PA_AM_XX_NHB)  +
                          mw[202] * Pct_MD_XX_NHB * PA_MD_XX_NHB  +  mw[252] * Pct_MD_XX_NHB * (1 - PA_MD_XX_NHB)  +
                          mw[302] * Pct_PM_XX_NHB * PA_PM_XX_NHB  +  mw[352] * Pct_PM_XX_NHB * (1 - PA_PM_XX_NHB)  +
                          mw[402] * Pct_EV_XX_NHB * PA_EV_XX_NHB  +  mw[452] * Pct_EV_XX_NHB * (1 - PA_EV_XX_NHB)   
                
                mw[540] = mw[102] * Pct_AM_XX_HBS * PA_AM_XX_HBS  +  mw[152] * Pct_AM_XX_HBS * (1 - PA_AM_XX_HBS)  +
                          mw[202] * Pct_MD_XX_HBS * PA_MD_XX_HBS  +  mw[252] * Pct_MD_XX_HBS * (1 - PA_MD_XX_HBS)  +
                          mw[302] * Pct_PM_XX_HBS * PA_PM_XX_HBS  +  mw[352] * Pct_PM_XX_HBS * (1 - PA_PM_XX_HBS)  +
                          mw[402] * Pct_EV_XX_HBS * PA_EV_XX_HBS  +  mw[452] * Pct_EV_XX_HBS * (1 - PA_EV_XX_HBS)   
                
                mw[550] = mw[102] * Pct_AM_XX_HBC * PA_AM_XX_HBC  +  mw[152] * Pct_AM_XX_HBC * (1 - PA_AM_XX_HBC)  +
                          mw[202] * Pct_MD_XX_HBC * PA_MD_XX_HBC  +  mw[252] * Pct_MD_XX_HBC * (1 - PA_MD_XX_HBC)  +
                          mw[302] * Pct_PM_XX_HBC * PA_PM_XX_HBC  +  mw[352] * Pct_PM_XX_HBC * (1 - PA_PM_XX_HBC)  +
                          mw[402] * Pct_EV_XX_HBC * PA_EV_XX_HBC  +  mw[452] * Pct_EV_XX_HBC * (1 - PA_EV_XX_HBC)   
                
                mw[560] = mw[102] * Pct_AM_XX_Rec * PA_AM_XX_Rec  +  mw[152] * Pct_AM_XX_Rec * (1 - PA_AM_XX_Rec)  +
                          mw[202] * Pct_MD_XX_Rec * PA_MD_XX_Rec  +  mw[252] * Pct_MD_XX_Rec * (1 - PA_MD_XX_Rec)  +
                          mw[302] * Pct_PM_XX_Rec * PA_PM_XX_Rec  +  mw[352] * Pct_PM_XX_Rec * (1 - PA_PM_XX_Rec)  +
                          mw[402] * Pct_EV_XX_Rec * PA_EV_XX_Rec  +  mw[452] * Pct_EV_XX_Rec * (1 - PA_EV_XX_Rec)   
                
                
                ;light truck skim
                mw[570] = mw[104] * Pct_AM_XX_LT * PA_AM_XX_LT  +  mw[154] * Pct_AM_XX_LT * (1 - PA_AM_XX_LT)  +
                          mw[204] * Pct_MD_XX_LT * PA_MD_XX_LT  +  mw[254] * Pct_MD_XX_LT * (1 - PA_MD_XX_LT)  +
                          mw[304] * Pct_PM_XX_LT * PA_PM_XX_LT  +  mw[354] * Pct_PM_XX_LT * (1 - PA_PM_XX_LT)  +
                          mw[404] * Pct_EV_XX_LT * PA_EV_XX_LT  +  mw[454] * Pct_EV_XX_LT * (1 - PA_EV_XX_LT)   
                
                
                ;medium truck skim
                mw[580] = mw[105] * Pct_AM_XX_MD * PA_AM_XX_MD  +  mw[155] * Pct_AM_XX_MD * (1 - PA_AM_XX_MD)  +
                          mw[205] * Pct_MD_XX_MD * PA_MD_XX_MD  +  mw[255] * Pct_MD_XX_MD * (1 - PA_MD_XX_MD)  +
                          mw[305] * Pct_PM_XX_MD * PA_PM_XX_MD  +  mw[355] * Pct_PM_XX_MD * (1 - PA_PM_XX_MD)  +
                          mw[405] * Pct_EV_XX_MD * PA_EV_XX_MD  +  mw[455] * Pct_EV_XX_MD * (1 - PA_EV_XX_MD)   
                
                
                ;heavy truck skim
                mw[590] = mw[106] * Pct_AM_XX_HV * PA_AM_XX_HV  +  mw[156] * Pct_AM_XX_HV * (1 - PA_AM_XX_HV)  +
                          mw[206] * Pct_MD_XX_HV * PA_MD_XX_HV  +  mw[256] * Pct_MD_XX_HV * (1 - PA_MD_XX_HV)  +
                          mw[306] * Pct_PM_XX_HV * PA_PM_XX_HV  +  mw[356] * Pct_PM_XX_HV * (1 - PA_PM_XX_HV)  +
                          mw[406] * Pct_EV_XX_HV * PA_EV_XX_HV  +  mw[456] * Pct_EV_XX_HV * (1 - PA_EV_XX_HV)   
                
            endif  ;by movement
            
        ENDJLOOP
        
    ENDRUN
    
ENDLOOP  ;_LOS=1, 2




;print timestamp
RUN PGM=MATRIX
    
    ZONES = 1
    
    SubScriptEndTime_TD = currenttime()
    SubScriptRunTime_TD = SubScriptEndTime_TD - @SubScriptStartTime_TD@
    
    ScriptEndTime = currenttime()
    ScriptRunTime = ScriptEndTime - @ScriptStartTime@
    
    PRINT FILE='@ScenarioDir@\_Log\_RunTime.txt',
        APPEND=T,
        LIST='\n        Finish time & dist avg DY skims   ', formatdatetime(SubScriptRunTime_TD, 40, 0, 'hhh:nn:ss'),
             '\n',
             '\n        Total Distribution                ', formatdatetime(ScriptRunTime, 40, 0, 'hhh:nn:ss')
    
ENDRUN




